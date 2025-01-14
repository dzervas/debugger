# Building

- Update to the latest development build of Binary Ninja 
  - Follow [this](https://docs.binary.ninja/guide/index.html#support) guide to do so

- Clone `binaryninja-api` and checkout to the corresponding commit used to build the version of Binary Ninja you are running
  - If you updated to the latest dev build of Binary Ninja, then you can checkout the api repo to the latest dev as well
  - A more robust approach is to find the file `api_REVISION.txt` in `BN_INSTALLATION_FOLDER/Resources`

```bash
git clone https://github.com/Vector35/binaryninja-api.git
cd binaryninja-api
git checkout dev
# or git checkout commit_hash
```

- Download LLDB development build for your OS at https://github.com/Vector35/lldb-artifacts/releases - make sure that the correct LLDB version is downloaded (`grep 'LLVM_VERSION ' core/CMakeLists.txt` can help)
  - Extract the zip archive to `~/libclang`

- Download Qt development build for your OS at https://github.com/Vector35/qt-artifacts/releases.
  - Extract the zip archive to `~/Qt`

- Build the debugger

```bash
# Get the source
git clone https://github.com/Vector35/debugger.git

# Do an out-of-source build
mkdir -p build
cd build

# Build it
cmake -DBN_API_PATH=../binaryninja-api -DBN_INSTALL_DIR=/path/to/binaryninja/installation ..

make
```

While the code is compiling, it's a good time to check the [Binary Ninja slack](https://slack.binary.ninja) for any updates!

The build artifacts will be in the folder `out`. You should find two files `libdebuggercore` and `libdebuggerui`, and two folders `python` and `lldb`. 

- Run the debugger
  - Open Binary Ninja, disable the setting `corePlugins.debugger` so the debugger that comes with Binary Ninja is not loaded
  - Close Binary Ninja
  - Copy everything in the `out` folder to the user plugin folder - `cp -r out/plugins/* ~/.binaryninja/plugins/`
  - Set the environment variable `BN_STANDALONE_DEBUGGER=1`
  - Launch BinaryNinja
