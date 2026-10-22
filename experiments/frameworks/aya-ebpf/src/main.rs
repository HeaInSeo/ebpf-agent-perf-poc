#![no_std]
#![no_main]

use aya_ebpf::{helpers::bpf_get_current_pid_tgid, macros::{map, tracepoint}, maps::{Array, PerCpuArray}, programs::TracePointContext};

#[map]
static CONFIG: Array<u32> = Array::with_max_entries(1, 0);
#[map]
static COUNTS: PerCpuArray<u64> = PerCpuArray::with_max_entries(1, 0);

#[tracepoint]
pub fn count_getpid(ctx: TracePointContext) -> u32 {
    if let Some(target) = CONFIG.get(0) {
        let id = unsafe { ctx.read_at::<i64>(8) };
        if (bpf_get_current_pid_tgid() >> 32) as u32 == *target && matches!(id, Ok(39)) {
            if let Some(value) = COUNTS.get_ptr_mut(0) {
                // CPU-local storage: this single-thread target has no concurrent writers.
                unsafe { *value += 1; }
            }
        }
    }
    0
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! { loop {} }
