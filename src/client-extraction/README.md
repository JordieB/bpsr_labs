# Client Extraction - C++ Metadata Extractor

## Overview

This C++ component extracts `global-metadata.dat` from the running Blue Protocol Star Resonance (BPSR) PC client during runtime. The extracted metadata file is then used by the C# orchestrator to process game data using Il2CppDumper and StarResonanceTool.

## Purpose

The C++ extractor is responsible for:
- Locating the running BPSR game process
- Extracting the `global-metadata.dat` file from the game's memory or installation directory
- Writing the metadata file to a location accessible by the C# orchestrator

## Architecture

```
C++ Extractor → global-metadata.dat → C# Orchestrator → Il2CppDumper/StarResonanceTool → Extracted Data
```

## Status

This component is currently in the initial setup phase. Implementation details will be added as development progresses.

## Build Requirements

- CMake 3.15 or later
- C++17 compatible compiler (MSVC, GCC, or Clang)
- Windows SDK (for process/memory access APIs)

## Future Implementation

The C++ extractor will need to:
1. Detect the BPSR game process
2. Locate or extract `global-metadata.dat` from the process
3. Save the file to a temporary or specified output location
4. Provide status/error reporting

