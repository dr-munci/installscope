#!/usr/bin/env python3
"""H1 ortam denemesi: bcc bu VM'de çalışıyor mu?

Her execve'de (yeni program başladığında) pid ve ppid'i yazar.
Çalıştırma:  sudo python3 collector/deneme_exec.py
Durdurma:    Ctrl+C

Bu dosya collector'ın kendisi değil; H2'de yazılacak collector'ın
ilk tohumu ve docs/ortam.md'deki sorunun kanıtıdır.
"""
from bcc import BPF

# Çekirdekte çalışacak eBPF programı (C).
# sched_process_exec tracepoint'i, execve başarıyla tamamlandığında tetiklenir.
# ppid'i çekirdek içinden (task->real_parent->tgid) okuyoruz, çünkü kısa ömürlü
# bir process bitince /proc/<pid> kaybolur ve kullanıcı alanından okumak geç kalır.
PROG = r"""
#include <linux/sched.h>
TRACEPOINT_PROBE(sched, sched_process_exec) {
    struct task_struct *t = (struct task_struct *)bpf_get_current_task();
    u32 ppid = t->real_parent->tgid;
    bpf_trace_printk("exec pid=%d ppid=%d\n", args->pid, ppid);
    return 0;
}
"""

# -fms-extensions NEDEN gerekli:
# Çekirdek 7.0 başlıklarında (include/linux/fs.h) struct filename, adı olmayan
# bir gömülü yapı (struct __filename_head;) kullanıyor. Bu söz dizimi ancak
# -fms-extensions ile geçerli. bcc bu bayrağı vermezse alan yok sayılır,
# yapı küçük çıkar ve static_assert(sizeof(struct filename) % 64 == 0) patlar.
# Ubuntu'nun hazır execsnoop-bpfcc aracı bu yüzden derlenmiyor (docs/ortam.md).
b = BPF(text=PROG, cflags=["-fms-extensions"])

print("Calisiyor! Ikinci terminalde bir komut calistir. Durdurmak icin Ctrl+C")
b.trace_print()  # /sys/kernel/debug/tracing/trace_pipe'ı okuyup ekrana basar
