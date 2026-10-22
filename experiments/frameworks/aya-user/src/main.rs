use aya::{maps::{Array, PerCpuArray}, programs::TracePoint, Ebpf};
use std::{env, error::Error};

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 { return Err("usage: collector PID OBJECT".into()); }
    let pid: u32 = args[1].parse()?;
    let mut set = unsafe { std::mem::zeroed::<libc::sigset_t>() };
    unsafe {
        libc::sigemptyset(&mut set);
        libc::sigaddset(&mut set, libc::SIGINT);
        libc::sigaddset(&mut set, libc::SIGTERM);
        if libc::pthread_sigmask(libc::SIG_BLOCK, &set, std::ptr::null_mut()) != 0 {
            return Err("pthread_sigmask failed".into());
        }
    }
    let mut bpf = Ebpf::load_file(&args[2])?;
    {
        let mut config = Array::<_, u32>::try_from(bpf.map_mut("CONFIG").ok_or("CONFIG missing")?)?;
        config.set(0, pid, 0)?;
    }
    let program: &mut TracePoint = bpf.program_mut("count_getpid").ok_or("program missing")?.try_into()?;
    program.load()?;
    program.attach("raw_syscalls", "sys_enter")?;
    println!("READY");
    use std::io::Write;
    std::io::stdout().flush()?;
    let mut received = 0;
    if unsafe { libc::sigwait(&set, &mut received) } != 0 { return Err("sigwait failed".into()); }
    let counts = PerCpuArray::<_, u64>::try_from(bpf.map("COUNTS").ok_or("COUNTS missing")?)?;
    let value: u64 = counts.get(&0, 0)?.iter().sum();
    drop(bpf);
    println!("{{\"observed\":{value}}}");
    Ok(())
}
