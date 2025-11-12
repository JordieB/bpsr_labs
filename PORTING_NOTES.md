# Porting Notes - sr-extract-orchestrator

Files ported from: D:\projects\bpsr-labs-dmine
Ported on: 2025-11-11 21:32:23

## Files Copied

- src\Il2CppMetadataDump\Il2CppMetadataDump.csproj - Il2CppMetadataDump project file
- src\Il2CppMetadataDump\Program.cs - Il2CppMetadataDump source code
- src\Orchestrator.Cli\Orchestrator.Cli.csproj - Orchestrator.Cli project file
- src\Orchestrator.Cli\Program.cs - Orchestrator.Cli source code
- scripts\dump.ps1 - Metadata dump script
- scripts\extract.ps1 - PKG extraction script
- scripts\import-dotenv.ps1 - Environment variable loader script
- scripts\setup.ps1 - Setup script for vendor tools
- .env.example - Environment configuration template
- Directory.Build.props - Build configuration (check if target repo has one)


## Next Steps

1. **Add NuGet Package**: Ensure DotNetEnv version 3.1.1 is referenced in both projects
   - src/Il2CppMetadataDump/Il2CppMetadataDump.csproj
   - src/Orchestrator.Cli/Orchestrator.Cli.csproj

2. **Update .gitignore**: Add these patterns if not present:
   \\\
   tools/
   output/
   DummyDll/
   \\\

3. **Handle Directory.Build.props**: 
   - If target repo already has one, merge the settings
   - Ensure TargetFramework is 
et8.0 and LangVersion is latest

4. **Vendor Tools**: The setup.ps1 script handles fetching Il2CppDumper and StarResonanceTool.
   - If target repo uses different dependency management, adapt accordingly
   - Or keep the script as-is if it fits your workflow

5. **Documentation**: Extract relevant sections from the original README.md:
   - Features section
   - Usage examples
   - Current Status
   - Future Ideas/Roadmap (if applicable)

6. **Solution File**: 
   - If you copied sr-extract-orchestrator.sln, add the projects to your main solution
   - Or integrate the projects into an existing solution

7. **Environment Variables**: Users will need to create .env from .env.example:
   - GAME_DIR
   - GAME_ASSEMBLY
   - OUTPUT_DIR
   - DUMMY_DLL

## Dependencies

- .NET 8 SDK
- PowerShell 5.1+ or PowerShell 7+
- Git (for setup script to fetch vendor tools)

## External Tools (handled by setup.ps1)

- Il2CppDumper: https://github.com/Perfare/Il2CppDumper
- StarResonanceTool: https://github.com/PotRooms/StarResonanceTool
