/*
 * x64 native instance guard for World of Tanks 2.3.1.2 #921 / 2.3.1.10157.
 *
 * Architecture notes vs 0.9.22 (#1513):
 *  - 0.9.22 resolved Python C API and the WGC cleanup thunk from RVAs inside
 *    WorldOfTanks.exe.  2.3.1.2 ships a full x64 python27.dll, so the Python
 *    bridge is resolved via GetProcAddress instead of hard-coded RVAs.
 *  - The single-instance gate is no longer only "wot_client_mutex".  Static
 *    analysis of this build shows WOT_STARTUP_MUTEX (app.cpp) plus WGC AppMutex
 *    names (wgc_game_mtx_*, wgc_running_games_mtx).  Offline installs log a
 *    soft WGC failure ("Running WGC instance is not found"), so WGC mutexes
 *    may be absent; the startup mutex is the primary gate.
 *  - We never invent a cleanup thunk RVA.  release_client_guard enumerates
 *    named Mutex objects owned by this process and closes only names that match
 *    the validated patterns after probing they exist.  PE identity must match.
 *
 * PE identity (measured 2026-09-12 from the offline install):
 *   Machine        0x8664
 *   TimeDateStamp  0x6A759054
 *   ImageBase      0x0000000140000000
 *   SizeOfImage    0x0509F000
 */

#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#include <string.h>

/* ---- Python 2.7 bridge types (resolved from python27.dll) ---- */

typedef intptr_t vvg_pysize_t;

typedef struct _PyObject {
    vvg_pysize_t ob_refcnt;
    void *ob_type;
} PyObject;

typedef PyObject *(*PyCFunction)(PyObject *, PyObject *);

typedef struct _PyMethodDef {
    const char *ml_name;
    PyCFunction ml_meth;
    int ml_flags;
    const char *ml_doc;
} PyMethodDef;

typedef PyObject *(*PyInitModule4_64Fn)(
    const char *, PyMethodDef *, const char *, PyObject *, int);
typedef PyObject *(*PyIntFromLongFn)(long);

#define PYTHON_API_VERSION_27 1013
#define METH_NOARGS 0x0004

/* ---- Exact-build identity ---- */

#define EXPECTED_MACHINE 0x8664U
#define EXPECTED_PE_TIMESTAMP 0x6A759054U
#define EXPECTED_IMAGE_BASE 0x0000000140000000ULL
#define EXPECTED_IMAGE_SIZE 0x0509F000U

#define GUARD_STATUS_HOST_MISMATCH 1L
#define GUARD_STATUS_PYTHON_MISSING 2L
#define GUARD_STATUS_PYTHON_SYMBOLS 3L
#define GUARD_STATUS_HOLDER_UNREADABLE 4L
#define GUARD_STATUS_WRAPPER_MISSING 5L
#define GUARD_STATUS_WRAPPER_INVALID 6L
#define GUARD_STATUS_STATE_INVALID 7L
#define GUARD_STATUS_API_MISSING 8L
#define GUARD_STATUS_WGC_MODULE_MISSING 9L
#define GUARD_STATUS_API_INVALID 10L
#define GUARD_STATUS_CHILD_INVALID 11L
#define GUARD_STATUS_HOLDER_CHANGED 12L
#define GUARD_STATUS_API_NOT_CLEARED 13L
#define GUARD_STATUS_CHILD_NOT_CLEARED 14L
#define GUARD_STATUS_STATE_NOT_DISABLED 15L
#define GUARD_STATUS_MUTEX_STILL_EXISTS 16L
#define GUARD_STATUS_MUTEX_PROBE_FAILED 17L
#define GUARD_STATUS_ENUM_FAILED 18L
#define GUARD_STATUS_NO_TARGETS 19L
#define GUARD_STATUS_CLOSE_PARTIAL 20L
#define GUARD_STATUS_NOT_INITIALIZED 21L
#define GUARD_STATUS_ATMOSPHERE_UNSUPPORTED 22L

#define MAX_HIDDEN_WINDOWS 16U
#define NT_SUCCESS(Status) (((LONG)(Status)) >= 0)
#define STATUS_INFO_LENGTH_MISMATCH ((LONG)0xC0000004L)

static const WCHAR *const STARTUP_MUTEX_CANDIDATES[] = {
    L"WOT_STARTUP_MUTEX",
    L"Global\\WOT_STARTUP_MUTEX",
    L"Local\\WOT_STARTUP_MUTEX",
    L"wot_client_mutex",
    L"Global\\wot_client_mutex",
    L"wgc_running_games_mtx",
    L"Global\\wgc_running_games_mtx",
    L"Local\\wgc_running_games_mtx",
    L"wgcs_running_games_mtx",
    L"wgc360_running_games_mtx",
    0
};

typedef struct HiddenWindow {
    HWND handle;
    WINDOWPLACEMENT placement;
} HiddenWindow;

typedef struct HideContext {
    DWORD process_id;
    DWORD error_code;
} HideContext;

typedef struct _VVG_UNICODE_STRING {
    USHORT Length;
    USHORT MaximumLength;
    PWCH Buffer;
} VVG_UNICODE_STRING;

typedef struct _VVG_SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX {
    PVOID Object;
    ULONG_PTR UniqueProcessId;
    ULONG_PTR HandleValue;
    ULONG GrantedAccess;
    USHORT CreatorBackTraceIndex;
    USHORT ObjectTypeIndex;
    ULONG HandleAttributes;
    ULONG Reserved;
} VVG_SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX;

typedef struct _VVG_SYSTEM_HANDLE_INFORMATION_EX {
    ULONG_PTR NumberOfHandles;
    ULONG_PTR Reserved;
    VVG_SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX Handles[1];
} VVG_SYSTEM_HANDLE_INFORMATION_EX;

typedef LONG (NTAPI *NtQuerySystemInformationFn)(
    ULONG SystemInformationClass,
    PVOID SystemInformation,
    ULONG SystemInformationLength,
    PULONG ReturnLength);
typedef LONG (NTAPI *NtQueryObjectFn)(
    HANDLE Handle,
    ULONG ObjectInformationClass,
    PVOID ObjectInformation,
    ULONG ObjectInformationLength,
    PULONG ReturnLength);

#define SystemExtendedHandleInformation 64
#define ObjectNameInformation 1

static unsigned char *g_image_base = 0;
static PyIntFromLongFn g_py_int_from_long = 0;
static HiddenWindow g_hidden_windows[MAX_HIDDEN_WINDOWS];
static unsigned int g_hidden_window_count = 0;
static int g_python_ready = 0;
static NtQuerySystemInformationFn g_nt_query_system = 0;
static NtQueryObjectFn g_nt_query_object = 0;


static int readable_region(const void *address, SIZE_T bytes)
{
    MEMORY_BASIC_INFORMATION info;
    uintptr_t cursor = (uintptr_t)address;
    uintptr_t end;
    uintptr_t previous;
    DWORD protection;

    if (address == 0 || bytes == 0 ||
            bytes > (SIZE_T)((uintptr_t)-1 - cursor)) {
        return 0;
    }
    end = cursor + bytes;
    while (cursor < end) {
        if (VirtualQuery((const void *)cursor, &info, sizeof(info)) !=
                sizeof(info) || info.State != MEM_COMMIT) {
            return 0;
        }
        if ((info.Protect & PAGE_GUARD) != 0) {
            return 0;
        }
        protection = info.Protect & 0xffU;
        if (protection != PAGE_READONLY &&
                protection != PAGE_READWRITE &&
                protection != PAGE_WRITECOPY &&
                protection != PAGE_EXECUTE_READ &&
                protection != PAGE_EXECUTE_READWRITE &&
                protection != PAGE_EXECUTE_WRITECOPY) {
            return 0;
        }
        previous = cursor;
        cursor = (uintptr_t)info.BaseAddress + info.RegionSize;
        if (cursor <= previous) {
            return 0;
        }
    }
    return 1;
}


static int validate_host(unsigned char *base)
{
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS64 *nt;

    if ((uintptr_t)base != (uintptr_t)EXPECTED_IMAGE_BASE ||
            !readable_region(base, sizeof(IMAGE_DOS_HEADER))) {
        return 0;
    }
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
            dos->e_lfanew > 0x1000) {
        return 0;
    }
    nt = (IMAGE_NT_HEADERS64 *)(base + dos->e_lfanew);
    if (!readable_region(nt, sizeof(IMAGE_NT_HEADERS64)) ||
            nt->Signature != IMAGE_NT_SIGNATURE ||
            nt->FileHeader.Machine != EXPECTED_MACHINE ||
            nt->FileHeader.TimeDateStamp != EXPECTED_PE_TIMESTAMP ||
            nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
            (uint64_t)nt->OptionalHeader.ImageBase != EXPECTED_IMAGE_BASE ||
            nt->OptionalHeader.SizeOfImage != EXPECTED_IMAGE_SIZE) {
        return 0;
    }
    return 1;
}


static PyObject *python_int(long value)
{
    if (g_py_int_from_long == 0) {
        /* Resolve on demand if vvg_init_bridge has not run / failed early. */
        HMODULE python = GetModuleHandleW(L"python27.dll");
        if (python != 0) {
            g_py_int_from_long = (PyIntFromLongFn)(void *)
                GetProcAddress(python, "PyInt_FromLong");
        }
    }
    if (g_py_int_from_long == 0) {
        return 0;
    }
    return g_py_int_from_long(value);
}


static int load_nt_apis(void)
{
    HMODULE ntdll;
    if (g_nt_query_system != 0 && g_nt_query_object != 0) {
        return 1;
    }
    ntdll = GetModuleHandleW(L"ntdll.dll");
    if (ntdll == 0) {
        return 0;
    }
    g_nt_query_system = (NtQuerySystemInformationFn)
        (void *)GetProcAddress(ntdll, "NtQuerySystemInformation");
    g_nt_query_object = (NtQueryObjectFn)
        (void *)GetProcAddress(ntdll, "NtQueryObject");
    return g_nt_query_system != 0 && g_nt_query_object != 0;
}


static int wide_ci_contains(const WCHAR *hay, const WCHAR *needle)
{
    size_t nlen = 0;
    size_t hlen = 0;
    size_t i;
    size_t j;

    if (hay == 0 || needle == 0) {
        return 0;
    }
    while (needle[nlen] != L'\0') {
        ++nlen;
    }
    while (hay[hlen] != L'\0') {
        ++hlen;
    }
    if (nlen == 0 || hlen < nlen) {
        return 0;
    }
    for (i = 0; i + nlen <= hlen; ++i) {
        for (j = 0; j < nlen; ++j) {
            WCHAR a = hay[i + j];
            WCHAR b = needle[j];
            if (a >= L'A' && a <= L'Z') {
                a = (WCHAR)(a - L'A' + L'a');
            }
            if (b >= L'A' && b <= L'Z') {
                b = (WCHAR)(b - L'A' + L'a');
            }
            if (a != b) {
                break;
            }
        }
        if (j == nlen) {
            return 1;
        }
    }
    return 0;
}


static int name_is_target_mutex(const WCHAR *name)
{
    static const WCHAR *const SUBSTRINGS[] = {
        L"WOT_STARTUP_MUTEX",
        L"wot_client_mutex",
        L"wgc_running_games_mtx",
        L"wgcs_running_games_mtx",
        L"wgc360_running_games_mtx",
        L"wgc_game_mtx_",
        L"AppMutex",
        0
    };
    unsigned i;
    if (name == 0 || name[0] == L'\0') {
        return 0;
    }
    for (i = 0; SUBSTRINGS[i] != 0; ++i) {
        if (wide_ci_contains(name, SUBSTRINGS[i])) {
            return 1;
        }
    }
    return 0;
}


static int probe_named_mutex_exists(const WCHAR *name)
{
    HANDLE probe;
    DWORD err;

    SetLastError(ERROR_SUCCESS);
    probe = OpenMutexW(SYNCHRONIZE, FALSE, name);
    if (probe != 0) {
        CloseHandle(probe);
        return 1;
    }
    err = GetLastError();
    if (err == ERROR_FILE_NOT_FOUND || err == ERROR_INVALID_NAME) {
        return 0;
    }
    return err == ERROR_ACCESS_DENIED;
}


static long verify_startup_mutex_absent(void)
{
    unsigned i;

    for (i = 0; STARTUP_MUTEX_CANDIDATES[i] != 0; ++i) {
        if (probe_named_mutex_exists(STARTUP_MUTEX_CANDIDATES[i])) {
            return GUARD_STATUS_MUTEX_STILL_EXISTS;
        }
    }
    return 0;
}


static int query_handle_name(HANDLE handle, WCHAR *buffer, DWORD buffer_chars)
{
    ULONG length = 0;
    LONG status;
    BYTE stack_buffer[1024];
    VVG_UNICODE_STRING *header;

    buffer[0] = L'\0';
    (void)g_nt_query_object(handle, ObjectNameInformation, 0, 0, &length);
    if (length < sizeof(VVG_UNICODE_STRING)) {
        length = sizeof(VVG_UNICODE_STRING) + 512;
    }
    if (length > sizeof(stack_buffer)) {
        return 0;
    }
    header = (VVG_UNICODE_STRING *)stack_buffer;
    ZeroMemory(stack_buffer, sizeof(stack_buffer));
    status = g_nt_query_object(handle, ObjectNameInformation,
        stack_buffer, length, &length);
    if (!NT_SUCCESS(status)) {
        return 0;
    }
    if (header->Buffer == 0 || header->Length == 0) {
        return 1;
    }
    {
        DWORD chars = header->Length / sizeof(WCHAR);
        if (chars >= buffer_chars) {
            chars = buffer_chars - 1;
        }
        CopyMemory(buffer, header->Buffer, chars * sizeof(WCHAR));
        buffer[chars] = L'\0';
    }
    return 1;
}


static long release_target_mutex_handles(void)
{
    ULONG buffer_size;
    ULONG return_length = 0;
    VVG_SYSTEM_HANDLE_INFORMATION_EX *info;
    BYTE *raw = 0;
    ULONG_PTR index;
    ULONG_PTR my_pid;
    unsigned int closed = 0;
    unsigned int matched = 0;
    LONG status;
    WCHAR name[260];

    if (!load_nt_apis()) {
        return GUARD_STATUS_ENUM_FAILED;
    }
    my_pid = (ULONG_PTR)GetCurrentProcessId();
    buffer_size = 1u << 20;
    for (;;) {
        raw = (BYTE *)HeapAlloc(GetProcessHeap(), 0, buffer_size);
        if (raw == 0) {
            return GUARD_STATUS_ENUM_FAILED;
        }
        status = g_nt_query_system(SystemExtendedHandleInformation,
            raw, buffer_size, &return_length);
        if (status == STATUS_INFO_LENGTH_MISMATCH) {
            HeapFree(GetProcessHeap(), 0, raw);
            raw = 0;
            buffer_size *= 2;
            if (buffer_size > (64u << 20)) {
                return GUARD_STATUS_ENUM_FAILED;
            }
            continue;
        }
        if (!NT_SUCCESS(status)) {
            HeapFree(GetProcessHeap(), 0, raw);
            return GUARD_STATUS_ENUM_FAILED;
        }
        break;
    }
    info = (VVG_SYSTEM_HANDLE_INFORMATION_EX *)raw;
    for (index = 0; index < info->NumberOfHandles; ++index) {
        const VVG_SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX *entry =
            &info->Handles[index];
        HANDLE handle;
        if (entry->UniqueProcessId != my_pid) {
            continue;
        }
        handle = (HANDLE)entry->HandleValue;
        if (!query_handle_name(handle, name, 260)) {
            continue;
        }
        if (!name_is_target_mutex(name)) {
            continue;
        }
        ++matched;
        ReleaseMutex(handle);
        if (CloseHandle(handle)) {
            ++closed;
        }
    }
    HeapFree(GetProcessHeap(), 0, raw);

    if (matched == 0) {
        return verify_startup_mutex_absent();
    }
    if (closed == 0) {
        return GUARD_STATUS_CLOSE_PARTIAL;
    }
    return verify_startup_mutex_absent();
}


static PyObject *release_client_guard(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    if (!g_python_ready || g_image_base == 0) {
        return python_int(GUARD_STATUS_NOT_INITIALIZED);
    }
    return python_int(release_target_mutex_handles());
}


static PyObject *install_atmosphere_owner_guard(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    return python_int(GUARD_STATUS_ATMOSPHERE_UNSUPPORTED);
}


static PyObject *probe_startup_mutex(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    return python_int(verify_startup_mutex_absent());
}


static int hidden_window_index(HWND handle)
{
    unsigned int index;
    for (index = 0; index < g_hidden_window_count; ++index) {
        if (g_hidden_windows[index].handle == handle) {
            return (int)index;
        }
    }
    return -1;
}


static BOOL CALLBACK hide_window_callback(HWND handle, LPARAM parameter)
{
    HideContext *context = (HideContext *)parameter;
    DWORD process_id = 0;
    WINDOWPLACEMENT placement;

    GetWindowThreadProcessId(handle, &process_id);
    if (process_id != context->process_id || !IsWindowVisible(handle) ||
            hidden_window_index(handle) >= 0) {
        return TRUE;
    }
    if (g_hidden_window_count >= MAX_HIDDEN_WINDOWS) {
        context->error_code = ERROR_INSUFFICIENT_BUFFER;
        return FALSE;
    }
    ZeroMemory(&placement, sizeof(placement));
    placement.length = sizeof(placement);
    if (!GetWindowPlacement(handle, &placement)) {
        context->error_code = GetLastError();
        if (context->error_code == ERROR_SUCCESS) {
            context->error_code = ERROR_GEN_FAILURE;
        }
        return FALSE;
    }
    g_hidden_windows[g_hidden_window_count].handle = handle;
    g_hidden_windows[g_hidden_window_count].placement = placement;
    ++g_hidden_window_count;
    ShowWindow(handle, SW_HIDE);
    return TRUE;
}


static void restore_hidden_range(unsigned int first_index)
{
    while (g_hidden_window_count > first_index) {
        HiddenWindow *record = &g_hidden_windows[g_hidden_window_count - 1];
        if (IsWindow(record->handle)) {
            SetWindowPlacement(record->handle, &record->placement);
            ShowWindow(record->handle, record->placement.showCmd);
        }
        --g_hidden_window_count;
    }
}


static long hide_process_windows_internal(void)
{
    HideContext context;
    unsigned int previous_count = g_hidden_window_count;
    BOOL enumerated;

    context.process_id = GetCurrentProcessId();
    context.error_code = ERROR_SUCCESS;
    SetLastError(ERROR_SUCCESS);
    enumerated = EnumWindows(hide_window_callback, (LPARAM)&context);
    if (!enumerated) {
        if (context.error_code == ERROR_SUCCESS) {
            context.error_code = GetLastError();
        }
        if (context.error_code == ERROR_SUCCESS) {
            context.error_code = ERROR_GEN_FAILURE;
        }
        restore_hidden_range(previous_count);
        return -(long)context.error_code;
    }
    return (long)(g_hidden_window_count - previous_count);
}


static long show_process_windows_internal(void)
{
    unsigned int index;
    unsigned int remaining = 0;
    unsigned int restored = 0;
    DWORD process_id;
    DWORD current_process_id = GetCurrentProcessId();
    DWORD first_error = ERROR_SUCCESS;

    for (index = 0; index < g_hidden_window_count; ++index) {
        HiddenWindow *record = &g_hidden_windows[index];
        process_id = 0;
        if (!IsWindow(record->handle)) {
            continue;
        }
        GetWindowThreadProcessId(record->handle, &process_id);
        if (process_id != current_process_id) {
            continue;
        }
        if (!SetWindowPlacement(record->handle, &record->placement)) {
            if (first_error == ERROR_SUCCESS) {
                first_error = GetLastError();
                if (first_error == ERROR_SUCCESS) {
                    first_error = ERROR_GEN_FAILURE;
                }
            }
            if (remaining != index) {
                g_hidden_windows[remaining] = *record;
            }
            ++remaining;
            continue;
        }
        ShowWindow(record->handle, record->placement.showCmd);
        ++restored;
    }
    g_hidden_window_count = remaining;
    if (first_error != ERROR_SUCCESS) {
        return -(long)first_error;
    }
    return (long)restored;
}


static PyObject *hide_process_windows(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    return python_int(hide_process_windows_internal());
}


static PyObject *show_process_windows(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    return python_int(show_process_windows_internal());
}


__declspec(dllexport) long __cdecl vvg_release_client_guard(void)
{
    if (!g_python_ready || g_image_base == 0) {
        return GUARD_STATUS_NOT_INITIALIZED;
    }
    return release_target_mutex_handles();
}


__declspec(dllexport) long __cdecl vvg_probe_startup_mutex(void)
{
    return verify_startup_mutex_absent();
}


__declspec(dllexport) long __cdecl vvg_install_atmosphere_owner_guard(void)
{
    return GUARD_STATUS_ATMOSPHERE_UNSUPPORTED;
}


__declspec(dllexport) long __cdecl vvg_hide_process_windows(void)
{
    return hide_process_windows_internal();
}


__declspec(dllexport) long __cdecl vvg_show_process_windows(void)
{
    return show_process_windows_internal();
}


__declspec(dllexport) long __cdecl vvg_validate_host(void)
{
    unsigned char *base = (unsigned char *)GetModuleHandleW(0);
    return validate_host(base) ? 0L : GUARD_STATUS_HOST_MISMATCH;
}


__declspec(dllexport) int __cdecl vvg_init_bridge(void)
{
    unsigned char *base = (unsigned char *)GetModuleHandleW(0);
    HMODULE python;

    /*
     * Always resolve Python symbols first so extension methods can return
     * PyInt even when host PE validation fails (unit tests / non-game hosts).
     * g_python_ready + g_image_base still gate mutex release.
     */
    python = GetModuleHandleW(L"python27.dll");
    if (python == 0) {
        g_image_base = 0;
        g_python_ready = 0;
        g_py_int_from_long = 0;
        return 0;
    }
    g_py_int_from_long = (PyIntFromLongFn)(void *)
        GetProcAddress(python, "PyInt_FromLong");
    if (g_py_int_from_long == 0) {
        g_image_base = 0;
        g_python_ready = 0;
        return 0;
    }
    (void)load_nt_apis();
    if (!validate_host(base)) {
        g_image_base = 0;
        g_python_ready = 0;
        return 0;
    }
    g_image_base = base;
    g_python_ready = 1;
    return 1;
}


/* C exports used by the Python extension wrappers below. */
__declspec(dllexport) long __cdecl vvg_validate_host(void);
__declspec(dllexport) int __cdecl vvg_init_bridge(void);


static PyObject *validate_host_py(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    return python_int(vvg_validate_host());
}


static PyObject *init_bridge_py(PyObject *unused_self,
        PyObject *unused_args)
{
    (void)unused_self;
    (void)unused_args;
    return python_int((long)vvg_init_bridge());
}


static PyMethodDef MODULE_METHODS[] = {
    {
        "install_atmosphere_owner_guard", install_atmosphere_owner_guard,
        METH_NOARGS,
        "Atmosphere owner repair is not mapped for 2.3.1.2; returns 22."
    },
    {
        "release_client_guard", release_client_guard, METH_NOARGS,
        "Release named startup/WGC AppMutex objects held by this process."
    },
    {
        "probe_startup_mutex", probe_startup_mutex, METH_NOARGS,
        "Return 0 if no target startup/WGC mutex name is visible."
    },
    {
        "hide_process_windows", hide_process_windows, METH_NOARGS,
        "Hide visible top-level windows owned by the current process."
    },
    {
        "show_process_windows", show_process_windows, METH_NOARGS,
        "Restore top-level windows previously hidden by this module."
    },
    {
        "validate_host", validate_host_py, METH_NOARGS,
        "Return 0 when the host PE identity matches this build."
    },
    {
        "init_bridge", init_bridge_py, METH_NOARGS,
        "Resolve python27 symbols for the current host process."
    },
    {0, 0, 0, 0}
};


__declspec(dllexport) void __cdecl initvvg_instance_guard_native(void)
{
    PyInitModule4_64Fn init_module;

    /*
     * Always register methods even when vvg_init_bridge fails (host PE
     * mismatch outside the client, or python27 symbols missing).  Importing
     * as a C extension is the primary load path inside the game because the
     * embedded interpreter has no _ctypes.  Early-return without
     * Py_InitModule4_64 made imp.load_dynamic fail outside the game and
     * hid useful status codes.
     */
    (void)vvg_init_bridge();
    init_module = (PyInitModule4_64Fn)(void *)
        GetProcAddress(GetModuleHandleW(L"python27.dll"), "Py_InitModule4_64");
    if (init_module == 0) {
        return;
    }
    init_module(
        "vvg_instance_guard_native", MODULE_METHODS,
        "WoT 2.3.1.2 x64 multi-client bridge.", 0,
        PYTHON_API_VERSION_27);
}


__declspec(dllexport) void __cdecl initinstance_guard_native(void)
{
    initvvg_instance_guard_native();
}
