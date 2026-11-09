// izleyici.c — çekirdekte çalışan eBPF programı (bcc derler, collector.py yükler).
//
// Ne yapar: Yalnızca kurulum komutunun ve onun soyundan gelen process'lerin
// execve, openat ve connect olaylarını yakalayıp kullanıcı alanına gönderir.
//
// Neden filtre çekirdekte: Sistemde her saniye yüzlerce openat olur. Hepsini
// kullanıcı alanına taşıyıp orada elemek perf buffer'ı doldurur ve olay
// kaybına yol açar (M3, KG4). Bu yüzden "izlenen" adlı bir haritada kurulum
// ağacındaki PID'leri tutuyoruz ve ağaç dışındaki olayları hiç göndermiyoruz.

#include <linux/sched.h>

// Olay tipleri (collector.py'deki TIPLER ile aynı sıra)
#define TIP_EXEC    1
#define TIP_OPEN    2
#define TIP_CONNECT 3

// Adres aileleri: başlık dosyası eklememek için sayıları elle yazıyoruz
#define AILE_INET  2   // AF_INET  (IPv4)
#define AILE_INET6 10  // AF_INET6 (IPv6)

// Kullanıcı alanına giden tek olay kaydı.
struct olay {
    u64  ts_ns;       // çekirdek saati (açılıştan beri ns, monoton)
    u32  pid;         // process kimliği (tgid; thread'ler aynı pid'i paylaşır)
    u32  ppid;        // ebeveyn process (real_parent->tgid)
    u32  tip;         // TIP_EXEC / TIP_OPEN / TIP_CONNECT
    u32  bayrak;      // openat bayrakları (okuma mı yazma mı)
    u16  aile;        // connect: adres ailesi
    u16  port;        // connect: port (ağ bayt sırasıyla)
    u8   adres[16];   // connect: IPv4 (ilk 4 bayt) ya da IPv6 adresi
    char comm[16];    // process adı
    char detay[256];  // exec: program yolu, openat: dosya yolu
};

BPF_PERF_OUTPUT(olaylar);                 // kullanıcı alanına olay kanalı
BPF_HASH(izlenen, u32, u32, 16384);       // kurulum ağacındaki PID'ler
BPF_PERCPU_ARRAY(tampon, struct olay, 1); // olayı hazırlamak için çalışma alanı
// Neden tampon: struct olay 320 bayt. eBPF yığını 512 bayt ile sınırlı;
// olayı yığında değil CPU başına ayrılmış bu alanda hazırlamak daha güvenli.

// Şu anki process kurulum ağacında mı?
static inline int izleniyor_mu(void) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;  // üst 32 bit = tgid
    return izlenen.lookup(&pid) != 0;
}

// Boş bir olay kaydı hazırlar ve ortak alanları (zaman, pid, ppid, ad) doldurur.
// ppid'i çekirdekten okuyoruz: kısa ömürlü process bitince /proc/<pid> kaybolur.
static inline struct olay *olay_baslat(u32 tip) {
    u32 sifir = 0;
    struct olay *o = tampon.lookup(&sifir);
    if (!o)
        return 0;
    __builtin_memset(o, 0, sizeof(*o));
    struct task_struct *t = (struct task_struct *)bpf_get_current_task();
    o->ts_ns = bpf_ktime_get_ns();
    o->pid = bpf_get_current_pid_tgid() >> 32;
    o->ppid = t->real_parent->tgid;
    o->tip = tip;
    bpf_get_current_comm(&o->comm, sizeof(o->comm));
    return o;
}

// fork/clone: ebeveyn izleniyorsa çocuğu da izlenenlere ekle.
// Böylece ağaç kendiliğinden büyür: pip → python → gcc → ... hepsi yakalanır.
TRACEPOINT_PROBE(sched, sched_process_fork) {
    u32 ebeveyn = args->parent_pid;
    if (izlenen.lookup(&ebeveyn) == 0)
        return 0;
    u32 cocuk = args->child_pid;
    u32 bir = 1;
    izlenen.update(&cocuk, &bir);
    return 0;
}

// Process (ya da thread) bitince haritadan sil.
// Neden: PID'ler yeniden kullanılır; silmezsek alakasız bir process aynı
// PID'i alıp yanlışlıkla izlenebilir.
TRACEPOINT_PROBE(sched, sched_process_exit) {
    u32 tid = bpf_get_current_pid_tgid();  // alt 32 bit = thread kimliği
    izlenen.delete(&tid);
    return 0;
}

// execve başarılı oldu: yeni program yüklendi.
TRACEPOINT_PROBE(sched, sched_process_exec) {
    if (!izleniyor_mu())
        return 0;
    struct olay *o = olay_baslat(TIP_EXEC);
    if (!o)
        return 0;
    TP_DATA_LOC_READ_STR(o->detay, filename, sizeof(o->detay));
    olaylar.perf_submit(args, o, sizeof(*o));
    return 0;
}

// openat çağrısı: dosya açma isteği (girişte yakalıyoruz; sonucu v0'da yok).
TRACEPOINT_PROBE(syscalls, sys_enter_openat) {
    if (!izleniyor_mu())
        return 0;
    struct olay *o = olay_baslat(TIP_OPEN);
    if (!o)
        return 0;
    o->bayrak = args->flags;
    bpf_probe_read_user_str(&o->detay, sizeof(o->detay), args->filename);
    olaylar.perf_submit(args, o, sizeof(*o));
    return 0;
}

// connect çağrısı: yalnızca IPv4/IPv6 bağlantılarını kaydediyoruz
// (yerel UNIX soketleri ağ bağlantısı değil).
TRACEPOINT_PROBE(syscalls, sys_enter_connect) {
    if (!izleniyor_mu())
        return 0;
    u16 aile = 0;
    const char *sa = (const char *)args->uservaddr;
    bpf_probe_read_user(&aile, sizeof(aile), sa);  // sockaddr'ın ilk 2 baytı
    if (aile != AILE_INET && aile != AILE_INET6)
        return 0;
    struct olay *o = olay_baslat(TIP_CONNECT);
    if (!o)
        return 0;
    o->aile = aile;
    // sockaddr_in ve sockaddr_in6'da port 2. bayttan başlar.
    bpf_probe_read_user(&o->port, sizeof(o->port), sa + 2);
    if (aile == AILE_INET)
        bpf_probe_read_user(&o->adres, 4, sa + 4);   // sin_addr
    else
        bpf_probe_read_user(&o->adres, 16, sa + 8);  // sin6_addr
    olaylar.perf_submit(args, o, sizeof(*o));
    return 0;
}
