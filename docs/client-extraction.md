# Client Extraction Feature

## Overview

The client extraction feature enables extraction of game data directly from the Blue Protocol Star Resonance (BPSR) PC client. This includes extracting `global-metadata.dat` during runtime and using it with Il2CppDumper and StarResonanceTool to extract protobufs, tables, and other game assets.

## Architecture

The client extraction feature consists of three main components:

```
┌─────────────────────┐
│  C++ Extractor      │  Extracts global-metadata.dat from running BPSR process
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  C# Orchestrator    │  Coordinates Il2CppDumper and StarResonanceTool
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Vendor Tools       │  Il2CppDumper + StarResonanceTool
│  - Il2CppDumper     │  Extract metadata and generate dummy DLLs
│  - StarResonanceTool│  Extract PKG files (protobufs, tables, etc.)
└─────────────────────┘
```

## Components

### 1. C++ Metadata Extractor

**Location**: `src/client-extraction/`

Extracts `global-metadata.dat` from the running BPSR game process. This component:
- Locates the running BPSR game process
- Extracts the `global-metadata.dat` file
- Saves it to a location accessible by the C# orchestrator

**Status**: Initial setup complete, implementation in progress.

### 2. C# Orchestrator

**Location**: `src/Orchestrator.Cli/`

Coordinates the execution of vendor tools (Il2CppDumper and StarResonanceTool) to process the extracted metadata and game files.

**Status**: Ported from external repository, ready for integration.

### 3. Il2CppMetadataDump

**Location**: `src/Il2CppMetadataDump/`

A utility project for dumping Il2Cpp metadata.

**Status**: Ported from external repository, ready for integration.

## Setup

### Prerequisites

- .NET 8 SDK
- CMake 3.15+ (for C++ component)
- C++17 compatible compiler
- PowerShell 5.1+ or PowerShell 7+
- Git (for fetching vendor tools)

### Initial Setup

1. **Set up vendor tools**:
   ```powershell
   .\scripts\setup.ps1
   ```
   This script fetches Il2CppDumper and StarResonanceTool to the `tools/` directory.

2. **Configure environment variables**:
   Copy `.env.example` to `.env` and configure:
   ```env
   GAME_DIR=C:\path\to\bpsr\game
   GAME_ASSEMBLY=C:\path\to\GameAssembly.dll
   OUTPUT_DIR=C:\path\to\output
   DUMMY_DLL=C:\path\to\Il2CppDumper\DummyDll
   ```

3. **Build C# projects**:
   ```powershell
   dotnet build src/Orchestrator.Cli/Orchestrator.Cli.csproj
   dotnet build src/Il2CppMetadataDump/Il2CppMetadataDump.csproj
   ```

4. **Build C++ extractor** (when implemented):
   ```powershell
   mkdir build
   cd build
   cmake ../src/client-extraction
   cmake --build .
   ```

## Usage

### Extracting Metadata

1. **Run the C++ extractor** (when implemented):
   ```powershell
   .\build\bin\client-extraction.exe
   ```
   This extracts `global-metadata.dat` from the running game.

2. **Run the orchestrator**:
   ```powershell
   .\scripts\dump.ps1
   ```
   This uses Il2CppDumper to process the metadata.

### Extracting PKG Files

```powershell
.\scripts\extract.ps1
```

This uses StarResonanceTool to extract protobufs, tables, and other assets from PKG files.

## Integration with Existing Tools

The client extraction feature is complementary to the existing Python packet analysis tools:

- **Packet Analysis**: Analyzes network traffic (existing Python tools)
- **Client Extraction**: Extracts game assets and metadata directly from the client (new C++/C# tools)

Both approaches can be used together to get a complete picture of the game's data structures and protocols.

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GAME_DIR` | Path to BPSR game installation | `C:\Games\BPSR` |
| `GAME_ASSEMBLY` | Path to GameAssembly.dll | `C:\Games\BPSR\GameAssembly.dll` |
| `OUTPUT_DIR` | Output directory for extracted data | `C:\BPSR\extracted` |
| `DUMMY_DLL` | Path to Il2CppDumper DummyDll directory | `C:\tools\Il2CppDumper\DummyDll` |

## Scripts

- **`scripts/setup.ps1`**: Fetches and sets up vendor tools (Il2CppDumper, StarResonanceTool)
- **`scripts/dump.ps1`**: Runs metadata dump using Il2CppDumper
- **`scripts/extract.ps1`**: Extracts PKG files using StarResonanceTool
- **`scripts/import-dotenv.ps1`**: Loads environment variables from `.env` file

## Future Development

- [ ] Complete C++ metadata extractor implementation
- [ ] Integration testing with live game process
- [ ] Automated extraction pipeline
- [ ] Integration with Python tooling for unified workflow

## Troubleshooting

### Vendor tools not found

Run `.\scripts\setup.ps1` to fetch the required tools.

### Environment variables not loaded

Ensure `.env` file exists and use `.\scripts\import-dotenv.ps1` to load variables in your PowerShell session.

### Build errors

- Ensure .NET 8 SDK is installed: `dotnet --version`
- For C++ builds, ensure CMake and a C++ compiler are installed

## Related Documentation

- [Setup Guide](setup.md) - General project setup
- [Command Reference](commands.md) - Python CLI commands
- [Packet Analysis Guide](packet-analysis.md) - Network packet analysis

