// Orchestrator.Cli — .NET 8 CLI for IL2CPP extraction orchestration
// Commands: dump, dummy, extract, --all

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using DotNetEnv;

class Program
{
    static int Main(string[] args)
    {
        try
        {
            // Load .env
            Env.TraversePath().Load();

            // Validate environment
            string gameDir = GetEnvRequired("GAME_DIR");
            string gameAssembly = GetEnvRequired("GAME_ASSEMBLY");
            string outputDir = GetEnvRequired("OUTPUT_DIR");
            string dummyDll = GetEnvRequired("DUMMY_DLL");

            // Validate paths
            ValidatePath(gameAssembly, "GAME_ASSEMBLY", "GameAssembly.dll not found");
            ValidateDirectory(gameDir, "GAME_DIR");

            // Check tools exist (using subdirectory structure)
            string toolsDir = Path.Combine(Directory.GetCurrentDirectory(), "tools");
            string il2CppDumper = Path.Combine(toolsDir, "Il2CppDumper", "Il2CppDumper.exe");
            string starResonanceTool = Path.Combine(toolsDir, "StarResonanceTool", "StarResonanceTool.exe");

            if (args.Length == 0 || args[0] == "--all")
            {
                return RunAll(gameAssembly, outputDir, dummyDll, il2CppDumper, starResonanceTool, gameDir);
            }

            string command = args[0].ToLowerInvariant();
            return command switch
            {
                "dump" => RunDump(gameAssembly),
                "dummy" => RunDummy(gameAssembly, outputDir, dummyDll, il2CppDumper),
                "extract" => RunExtract(gameDir, dummyDll, outputDir, starResonanceTool),
                _ => PrintUsage()
            };
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Error: {ex.Message}");
            return 1;
        }
    }

    static int RunAll(string gameAssembly, string outputDir, string dummyDll, string il2CppDumper, string starResonanceTool, string gameDir)
    {
        Console.WriteLine("=== Running complete extraction pipeline ===\n");

        // Step 1: Dump
        Console.WriteLine("[1/3] Dumping IL2CPP metadata...");
        if (RunDump(gameAssembly) != 0)
        {
            Console.Error.WriteLine("Dump failed. Aborting.");
            return 1;
        }

        // Step 2: Generate DummyDll
        Console.WriteLine("\n[2/3] Generating DummyDll...");
        if (RunDummy(gameAssembly, outputDir, dummyDll, il2CppDumper) != 0)
        {
            Console.Error.WriteLine("DummyDll generation failed. Aborting.");
            return 1;
        }

        // Step 3: Extract
        Console.WriteLine("\n[3/3] Extracting PKG files...");
        if (RunExtract(gameDir, dummyDll, outputDir, starResonanceTool) != 0)
        {
            Console.Error.WriteLine("Extraction failed. Aborting.");
            return 1;
        }

        PrintSummary(outputDir, dummyDll);
        return 0;
    }

    static int RunDump(string gameAssembly)
    {
        string dumperPath = Path.Combine(Directory.GetCurrentDirectory(), "src", "Il2CppMetadataDump", "bin", "Release", "net8.0", "Il2CppMetadataDump.exe");
        if (!File.Exists(dumperPath))
        {
            Console.Error.WriteLine($"Il2CppMetadataDump.exe not found. Build it first: dotnet build -c Release");
            return 1;
        }

        return RunProcess(dumperPath, "", "Failed to dump metadata");
    }

    static int RunDummy(string gameAssembly, string outputDir, string dummyDll, string il2CppDumper)
    {
        if (!File.Exists(il2CppDumper))
        {
            Console.Error.WriteLine($"Il2CppDumper.exe not found. Run setup first: scripts/setup.ps1");
            return 1;
        }

        string metadataPath = Path.Combine(outputDir, "global-metadata.dat");
        if (!File.Exists(metadataPath))
        {
            Console.Error.WriteLine($"Metadata file not found: {metadataPath}. Run dump first.");
            return 1;
        }

        string args = $"\"{gameAssembly}\" \"{metadataPath}\" \"{dummyDll}\"";
        return RunProcess(il2CppDumper, args, "Failed to generate DummyDll");
    }

    static int RunExtract(string gameDir, string dummyDll, string outputDir, string starResonanceTool)
    {
        if (!File.Exists(starResonanceTool))
        {
            Console.Error.WriteLine($"StarResonanceTool.exe not found. Run setup first: scripts/setup.ps1");
            return 1;
        }

        string pkgPath = Path.Combine(gameDir, "meta.pkg");
        if (!File.Exists(pkgPath))
        {
            Console.Error.WriteLine($"PKG file not found: {pkgPath}");
            return 1;
        }

        if (!Directory.Exists(dummyDll) || !Directory.EnumerateFiles(dummyDll, "*.dll").Any())
        {
            Console.Error.WriteLine($"DummyDll directory not found or empty: {dummyDll}. Run dummy first.");
            return 1;
        }

        string args = $"--pkg \"{pkgPath}\" --dll \"{dummyDll}\" --output \"{outputDir}\"";
        int result = RunProcess(starResonanceTool, args, "Failed to extract PKG files");

        if (result == 0)
        {
            string excelsDir = Path.Combine(outputDir, "Excels");
            if (Directory.Exists(excelsDir))
            {
                int fileCount = Directory.EnumerateFiles(excelsDir, "*.json", SearchOption.AllDirectories).Count();
                Console.WriteLine($"Extracted {fileCount} Excel JSON files to: {excelsDir}");
            }
        }

        return result;
    }

    static int RunProcess(string exePath, string arguments, string errorMessage)
    {
        var psi = new ProcessStartInfo
        {
            FileName = exePath,
            Arguments = arguments,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        using var process = Process.Start(psi);
        if (process == null)
        {
            Console.Error.WriteLine($"{errorMessage}: Failed to start process");
            return 1;
        }

        // Stream output
        process.OutputDataReceived += (sender, e) => { if (e.Data != null) Console.WriteLine(e.Data); };
        process.ErrorDataReceived += (sender, e) => { if (e.Data != null) Console.Error.WriteLine(e.Data); };

        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        process.WaitForExit();

        if (process.ExitCode != 0)
        {
            Console.Error.WriteLine($"{errorMessage} (exit code: {process.ExitCode})");
        }

        return process.ExitCode;
    }

    static void PrintSummary(string outputDir, string dummyDll)
    {
        Console.WriteLine("\n=== Extraction Complete ===");
        Console.WriteLine($"Output directory: {outputDir}");
        Console.WriteLine($"DummyDll directory: {dummyDll}");

        string excelsDir = Path.Combine(outputDir, "Excels");
        if (Directory.Exists(excelsDir))
        {
            int fileCount = Directory.EnumerateFiles(excelsDir, "*.json", SearchOption.AllDirectories).Count();
            Console.WriteLine($"Excels JSON files: {fileCount}");
        }

        Console.WriteLine("\nNext steps:");
        Console.WriteLine("  - Review extracted files in OUTPUT_DIR");
        Console.WriteLine("  - Proto files are in OUTPUT_DIR/Protos (no DummyDll required)");
        Console.WriteLine("  - Excel/ztables are in OUTPUT_DIR/Excels (DummyDll required)");
    }

    static int PrintUsage()
    {
        Console.WriteLine("Usage: orchestrator [command]");
        Console.WriteLine();
        Console.WriteLine("Commands:");
        Console.WriteLine("  dump      - Dump IL2CPP global-metadata.dat from running game");
        Console.WriteLine("  dummy     - Generate DummyDll from GameAssembly.dll + metadata");
        Console.WriteLine("  extract   - Extract PKG files (Excels/Lua/Bundles/Protos)");
        Console.WriteLine("  --all     - Run complete pipeline: dump → dummy → extract");
        Console.WriteLine();
        Console.WriteLine("Environment variables (from .env):");
        Console.WriteLine("  GAME_DIR      - Game installation directory");
        Console.WriteLine("  GAME_ASSEMBLY - Path to GameAssembly.dll");
        Console.WriteLine("  OUTPUT_DIR    - Output directory for extracted files");
        Console.WriteLine("  DUMMY_DLL     - Directory for generated DummyDll files");
        return 1;
    }

    static string GetEnvRequired(string key)
    {
        var value = Environment.GetEnvironmentVariable(key);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new Exception($"Required environment variable '{key}' not set. Check your .env file.");
        }
        return Environment.ExpandEnvironmentVariables(value);
    }

    static void ValidatePath(string path, string envVar, string errorMessage)
    {
        if (!File.Exists(path))
        {
            throw new Exception($"{errorMessage}. Check {envVar} in .env: {path}");
        }
    }

    static void ValidateDirectory(string path, string envVar)
    {
        if (!Directory.Exists(path))
        {
            throw new Exception($"Directory not found. Check {envVar} in .env: {path}");
        }
    }
}
