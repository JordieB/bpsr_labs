// Il2CppMetadataDump — net8.0
// Usage:
//   dotnet run -c Release -- [outPath] [maxMB]
//   dotnet run -c Release --            // auto-detect by GameAssembly.dll, default output
//
// Env (.env):
//   GAME_DIR=...                         (optional)
//   GAME_ASSEMBLY=%GAME_DIR%\GameAssembly.dll  (optional hint for auto-detect)
//   OUTPUT_DIR=D:\projects\...\output    (default dump dir)

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using DotNetEnv;

class Program
{
    // ---- Win32 interop ----
    const uint PROCESS_VM_READ = 0x0010;
    const uint PROCESS_QUERY_INFORMATION = 0x0400;

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, int pid);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, UIntPtr size, out UIntPtr read);

    [DllImport("kernel32.dll")]
    static extern UIntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MEMORY_BASIC_INFORMATION mbi, UIntPtr len);

    [StructLayout(LayoutKind.Sequential)]
    struct MEMORY_BASIC_INFORMATION
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public UIntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    static void Main(string[] args)
    {
        // ---- config from .env ----
        Env.TraversePath().Load(); // looks in cwd, then walks up to repo root

        string gameAssemblyHint = GetEnv("GAME_ASSEMBLY");
        string outputDir = GetEnv("OUTPUT_DIR", Directory.GetCurrentDirectory());

        // ---- resolve args ----
        // Args format: -- [outPath] [maxMB]
        // Skip "--" if present
        int argIndex = 0;
        if (args.Length > 0 && args[0] == "--")
            argIndex = 1;

        int pid = ResolveTargetPid(gameAssemblyHint);
        string outPath = ResolveOutPath(args, argIndex, outputDir);
        int maxMB = ResolveMaxMb(args, argIndex, 64);

        Console.WriteLine($"target pid: {pid}");
        Console.WriteLine($"output:     {outPath}");
        Console.WriteLine($"max cap:    {maxMB} MB");

        // ---- open & scan ----
        var h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid);
        if (h == IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());

        var headerAddr = FindMetadataHeader(h, out int ver);
        Console.WriteLine($"found metadata header @ 0x{headerAddr.ToInt64():X}, version {ver}");

        // dump exact (size computed from header) with safe caps
        DumpExact(h, headerAddr, outPath, maxMB);
        Console.WriteLine($"wrote {outPath}");
    }

    // ---------- helpers ----------

    static string GetEnv(string key, string fallback = "")
    {
        var v = Environment.GetEnvironmentVariable(key);
        return string.IsNullOrWhiteSpace(v) ? fallback : Environment.ExpandEnvironmentVariables(v);
    }

    static int ResolveTargetPid(string gameAssemblyHint)
    {
        // Auto-detect by module (GameAssembly.dll). Prefer hint path if provided.
        var byModule = FindProcessWithGameAssembly(gameAssemblyHint);
        if (byModule != null) return byModule.Id;

        throw new Exception("auto-detect failed; ensure game is running and loaded GameAssembly.dll.");
    }

    static string ResolveOutPath(string[] args, int argIndex, string outputDir)
    {
        if (args.Length > argIndex && !string.IsNullOrWhiteSpace(args[argIndex]))
            return Path.GetFullPath(args[argIndex]);

        Directory.CreateDirectory(outputDir);
        return Path.Combine(outputDir, "global-metadata.dat");
    }

    static int ResolveMaxMb(string[] args, int argIndex, int def)
    {
        if (args.Length > argIndex + 1 && int.TryParse(args[argIndex + 1], out var m)) return Math.Clamp(m, 8, 256);
        return def;
    }

    static Process? FindProcessWithGameAssembly(string hintPath)
    {
        var all = Process.GetProcesses();

        foreach (var p in all)
        {
            try
            {
                // Fast path: if user hinted the exact GameAssembly.dll path, see if the process loaded that path.
                if (!string.IsNullOrWhiteSpace(hintPath))
                {
                    var hasHint = p.Modules.Cast<ProcessModule>().Any(m =>
                        string.Equals(m.FileName, hintPath, StringComparison.OrdinalIgnoreCase));
                    if (hasHint) return p;
                }

                // Otherwise: look for any process that loaded GameAssembly.dll
                var hasIl2Cpp = p.Modules.Cast<ProcessModule>().Any(m =>
                    m.ModuleName.Equals("GameAssembly.dll", StringComparison.OrdinalIgnoreCase));
                if (hasIl2Cpp) return p;
            }
            catch
            {
                // access denied on some system processes; ignore
            }
        }
        return null;
    }

    static IntPtr FindMetadataHeader(IntPtr h, out int version)
    {
        var magic = new byte[] { 0xAF, 0x1B, 0xB1, 0xFA }; // 0xFAB11BAF LE
        var buf = new byte[128 * 1024];
        var mbiLen = (UIntPtr)Marshal.SizeOf<MEMORY_BASIC_INFORMATION>();
        IntPtr cursor = IntPtr.Zero;

        while (true)
        {
            if (VirtualQueryEx(h, cursor, out var mbi, mbiLen) == UIntPtr.Zero) break;

            bool committed = mbi.State == 0x1000; // MEM_COMMIT
            bool readable =
                mbi.Protect != 0x01 &&      // PAGE_NOACCESS
                mbi.Protect != 0x100 &&     // PAGE_GUARD
                (mbi.Protect & 0x0F) != 0;  // any readable

            if (committed && readable && mbi.RegionSize != UIntPtr.Zero)
            {
                ulong regionSize = mbi.RegionSize.ToUInt64();
                ulong offset = 0;
                while (offset < regionSize)
                {
                    int toRead = (int)Math.Min((ulong)buf.Length, regionSize - offset);
                    var addr = new IntPtr(mbi.BaseAddress.ToInt64() + (long)offset);
                    if (!Read(h, addr, buf, toRead, out int got) || got == 0) break;

                    for (int i = 0; i <= got - 8; i++)
                    {
                        if (buf[i] == magic[0] && buf[i + 1] == magic[1] && buf[i + 2] == magic[2] && buf[i + 3] == magic[3])
                        {
                            int ver = BitConverter.ToInt32(buf, i + 4);
                            if (ver >= 20 && ver <= 40)
                            {
                                version = ver;
                                return new IntPtr(mbi.BaseAddress.ToInt64() + (long)offset + i);
                            }
                        }
                    }
                    offset += (ulong)got;
                }
            }
            cursor = new IntPtr(mbi.BaseAddress.ToInt64() + (long)mbi.RegionSize.ToUInt64());
        }

        throw new Exception("global-metadata header not found — try after loading into a scene.");
    }

    static bool Read(IntPtr h, IntPtr addr, byte[] buf, int len, out int got)
    {
        bool ok = ReadProcessMemory(h, addr, buf, (UIntPtr)len, out var read);
        got = ok ? (int)read.ToUInt64() : 0;
        return ok;
    }

    static int ReadI32(IntPtr h, IntPtr addr)
    {
        var b = new byte[4];
        if (!ReadProcessMemory(h, addr, b, (UIntPtr)4, out var read) || read == UIntPtr.Zero) return 0;
        return BitConverter.ToInt32(b, 0);
    }

    // compute a conservative true size from header tables; then dump, capped by maxMB
    static void DumpExact(IntPtr h, IntPtr headerAddr, string outPath, int maxMB)
    {
        long size = ComputeMetadataSize(h, headerAddr);
        long cap = (long)maxMB * 1024 * 1024;
        if (size > cap) size = cap;

        using var fs = File.Create(outPath);
        var buf = new byte[128 * 1024];
        long readTotal = 0;

        while (readTotal < size)
        {
            int toRead = (int)Math.Min(buf.Length, size - readTotal);
            var ptr = new IntPtr(headerAddr.ToInt64() + readTotal);
            if (!ReadProcessMemory(h, ptr, buf, (UIntPtr)toRead, out var got) || got == UIntPtr.Zero) break;
            int n = (int)got.ToUInt64();
            fs.Write(buf, 0, n);
            readTotal += n;
            if (n < toRead) break;
        }
    }

    static long ComputeMetadataSize(IntPtr h, IntPtr headerAddr)
    {
        // magic(0) u32, version(4) i32, then many 8-byte (offset,count) pairs starting at 8
        int I32(long off) => ReadI32(h, new IntPtr(headerAddr.ToInt64() + off));

        // helper to get (offset,count) for pair index
        (int off, int cnt) Pair(int index)
        {
            long p = 8 + index * 8;
            return (I32(p), I32(p + 4));
        }

        // sample a robust subset that typically reaches EOF across v24..31+
        var tables = new (int idx, int elemSize)[]
        {
            (0,  8),  // stringLiteral
            (1,  1),  // stringLiteralData (bytes)
            (2,  4),  // strings
            (4, 32),  // events
            (5, 32),  // properties
            (6, 32),  // methods
            (7, 32),  // parameters
            (8, 32),  // fields
            (9, 24),  // typeDefinitions
            (11,24),  // images
            (12,32),  // assemblies
        };

        long maxEnd = 0;
        foreach (var t in tables)
        {
            var (off, cnt) = Pair(t.idx);
            if (off <= 0 || cnt <= 0) continue;
            long end = (long)off + (long)cnt * t.elemSize;
            if (end > maxEnd) maxEnd = end;
        }

        if (maxEnd < 1_000_000) maxEnd = 1_000_000; // at least ~1MB
        if (maxEnd > 128L * 1024 * 1024) maxEnd = 128L * 1024 * 1024; // clamp 128MB
        return maxEnd;
    }
}

