/*
 * Windowless / multi-instance starter for World of Tanks 2.3.1.2 x64.
 *
 * Ports the essential behaviour of the 0.9.22 offline_worker_starter.c:
 *  - Optional private desktop for hidden worker clients
 *  - Injects VVG_ALLOW_MULTIPLE_CLIENTS=1 for the instance guard Python side
 *  - Kill-on-close Job object so orphan workers die with the starter
 *  - Optional ready marker so the launcher can synchronize
 *
 * Modes:
 *   (default)  / --worker-only : start one client as hidden worker
 *   --player                 : start one visible player client
 *   --stop-starter <pid>     : signal a running starter to stop
 */

#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <strsafe.h>

#define WORKER_MUTEX_NAME L"Local\\vvg_offline_worker"
#define WORKER_MODE_ENV L"VVG_CLIENT_MODE"
#define WORKER_MODE_VALUE L"simulation_worker"
#define PLAYER_MODE_VALUE L"player"
#define MULTI_CLIENT_ENV L"VVG_ALLOW_MULTIPLE_CLIENTS"
#define MULTI_CLIENT_VALUE L"1"
#define GUARD_PATH_ENV L"VVG_INSTANCE_GUARD_PATH"
#define HIDDEN_DESKTOP_ENV L"VVG_HIDDEN_DESKTOP"
#define HIDDEN_DESKTOP_VALUE L"1"
#define WORKER_READY_MARKER_ENV L"VVG_WORKER_READY_MARKER"
#define WORKER_READY_MARKER_FILE L"vvg-worker.ready"
#define STARTER_STOP_COMMAND L"--stop-starter "
#define STARTER_STOP_EVENT_PREFIX L"Local\\VVGOfflineStarterStop_"
#define WORKER_READY_TIMEOUT_MS 90000
#define WORKER_READY_POLL_MS 100
#define STOP_TIMEOUT_MS 8000

static WCHAR g_root[MAX_PATH];


static void log_failure(const char *stage, DWORD error_code)
{
    WCHAR log_path[MAX_PATH];
    char message[256];
    DWORD written = 0;
    HANDLE file;

    if (FAILED(StringCchCopyW(log_path, MAX_PATH, g_root)) ||
            FAILED(StringCchCatW(log_path, MAX_PATH,
                L"vvg-worker-starter.log"))) {
        return;
    }
    file = CreateFileW(log_path, FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
        OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (FAILED(StringCchPrintfA(message, sizeof(message),
            "stage=%s win32_error=%lu\r\n", stage,
            (unsigned long)error_code))) {
        CloseHandle(file);
        return;
    }
    WriteFile(file, message, (DWORD)lstrlenA(message), &written, 0);
    CloseHandle(file);
}


static int resolve_game_root(WCHAR *game_path, size_t game_path_count)
{
    WCHAR starter_path[MAX_PATH];
    DWORD length;
    int index;

    length = GetModuleFileNameW(0, starter_path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return 0;
    }
    for (index = (int)length - 1; index >= 0; --index) {
        if (starter_path[index] == L'\\' || starter_path[index] == L'/') {
            starter_path[index + 1] = L'\0';
            break;
        }
    }
    if (index < 0 || FAILED(StringCchCopyW(g_root, MAX_PATH,
            starter_path)) || FAILED(StringCchCopyW(game_path,
            game_path_count, starter_path)) ||
            FAILED(StringCchCatW(game_path, game_path_count,
                L"WorldOfTanks.exe"))) {
        return 0;
    }
    return GetFileAttributesW(game_path) != INVALID_FILE_ATTRIBUTES;
}


static int configure_kill_job(HANDLE job)
{
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION info;

    ZeroMemory(&info, sizeof(info));
    info.BasicLimitInformation.LimitFlags =
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    return SetInformationJobObject(job, JobObjectExtendedLimitInformation,
        &info, sizeof(info)) != FALSE;
}


static int starter_stop_event_name(DWORD process_id, WCHAR *name,
        size_t name_count)
{
    return SUCCEEDED(StringCchPrintfW(name, name_count, L"%s%lu",
        STARTER_STOP_EVENT_PREFIX, (unsigned long)process_id));
}


static int parse_starter_stop_command(const WCHAR *command_line,
        DWORD *process_id)
{
    const WCHAR *cursor;
    DWORD value = 0;
    size_t prefix_length = lstrlenW(STARTER_STOP_COMMAND);

    if (wcsncmp(command_line, STARTER_STOP_COMMAND, prefix_length) != 0) {
        return 0;
    }
    cursor = command_line + prefix_length;
    if (*cursor == L'\0') {
        return -1;
    }
    while (*cursor != L'\0') {
        DWORD digit;
        if (*cursor < L'0' || *cursor > L'9') {
            return -1;
        }
        digit = (DWORD)(*cursor - L'0');
        if (value > (MAXDWORD - digit) / 10) {
            return -1;
        }
        value = value * 10 + digit;
        ++cursor;
    }
    if (value == 0) {
        return -1;
    }
    *process_id = value;
    return 1;
}


static int signal_starter_stop(DWORD process_id)
{
    WCHAR event_name[96];
    HANDLE stop_event;
    DWORD error_code;

    if (!starter_stop_event_name(process_id, event_name, 96)) {
        return 26;
    }
    stop_event = OpenEventW(EVENT_MODIFY_STATE, FALSE, event_name);
    if (stop_event == 0) {
        return 27;
    }
    if (!SetEvent(stop_event)) {
        error_code = GetLastError();
        CloseHandle(stop_event);
        SetLastError(error_code);
        return 28;
    }
    CloseHandle(stop_event);
    return 0;
}


static HANDLE create_starter_stop_event(void)
{
    WCHAR event_name[96];

    if (!starter_stop_event_name(GetCurrentProcessId(), event_name, 96)) {
        SetLastError(ERROR_INSUFFICIENT_BUFFER);
        return 0;
    }
    return CreateEventW(0, TRUE, FALSE, event_name);
}


static int publish_ready_marker(const WCHAR *marker_path)
{
    static const char payload[] = "ready\n";
    HANDLE file;
    DWORD written = 0;

    file = CreateFileW(marker_path, GENERIC_WRITE, FILE_SHARE_READ, 0,
        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!WriteFile(file, payload, sizeof(payload) - 1, &written, 0) ||
            written != sizeof(payload) - 1) {
        CloseHandle(file);
        DeleteFileW(marker_path);
        return 0;
    }
    CloseHandle(file);
    return 1;
}


static int wait_for_worker_ready(HANDLE worker_process, HANDLE stop_event,
        const WCHAR *marker_path)
{
    DWORD elapsed = 0;

    while (elapsed <= WORKER_READY_TIMEOUT_MS) {
        DWORD attrs;
        DWORD wait_state;
        if (stop_event != 0 &&
                WaitForSingleObject(stop_event, 0) == WAIT_OBJECT_0) {
            return -1;
        }
        wait_state = WaitForSingleObject(worker_process, 0);
        if (wait_state != WAIT_TIMEOUT) {
            return 0;
        }
        attrs = GetFileAttributesW(marker_path);
        if (attrs != INVALID_FILE_ATTRIBUTES &&
                !(attrs & FILE_ATTRIBUTE_DIRECTORY)) {
            wait_state = WaitForSingleObject(worker_process, 0);
            if (wait_state == WAIT_TIMEOUT) {
                return 1;
            }
            return 0;
        }
        Sleep(WORKER_READY_POLL_MS);
        elapsed += WORKER_READY_POLL_MS;
    }
    return 0;
}


static int configure_instance_guard_env(BOOL worker)
{
    WCHAR guard_path[MAX_PATH];

    /* Both worker and player clients must release WOT_STARTUP_MUTEX after
     * the game mod loads.  Clearing the flag for --player made a second
     * starter-launched client re-show "already running". */
    if (!SetEnvironmentVariableW(MULTI_CLIENT_ENV, MULTI_CLIENT_VALUE)) {
        return 0;
    }
    if (FAILED(StringCchCopyW(guard_path, MAX_PATH, g_root)) ||
            FAILED(StringCchCatW(guard_path, MAX_PATH,
                L"vvg_instance_guard_native.pyd"))) {
        return 0;
    }
    if (GetFileAttributesW(guard_path) == INVALID_FILE_ATTRIBUTES) {
        /* Prefer mods/<version>/ when the sidecar is not next to the exe. */
        if (FAILED(StringCchCopyW(guard_path, MAX_PATH, g_root)) ||
                FAILED(StringCchCatW(guard_path, MAX_PATH,
                    L"mods\\2.3.1.2\\vvg_instance_guard_native.pyd"))) {
            return 0;
        }
    }
    if (!SetEnvironmentVariableW(GUARD_PATH_ENV, guard_path)) {
        return 0;
    }
    if (worker) {
        if (!SetEnvironmentVariableW(WORKER_MODE_ENV, WORKER_MODE_VALUE)) {
            return 0;
        }
    } else {
        if (!SetEnvironmentVariableW(WORKER_MODE_ENV, PLAYER_MODE_VALUE)) {
            return 0;
        }
        SetEnvironmentVariableW(HIDDEN_DESKTOP_ENV, 0);
    }
    return 1;
}


static int launch_client(const WCHAR *game_path, BOOL worker,
        HANDLE stop_event)
{
    WCHAR child_command[2 * MAX_PATH];
    WCHAR ready_marker[MAX_PATH];
    WCHAR full_desktop_name[128];
    WCHAR desktop_name[96];
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    HANDLE job = 0;
    DWORD exit_code = 1;
    DWORD wait_state;
    int ready_state;
    int result = 1;

    ZeroMemory(&process, sizeof(process));
    ready_marker[0] = L'\0';

    if (!configure_instance_guard_env(worker)) {
        log_failure("configure_instance_guard_env", GetLastError());
        return worker ? 20 : 21;
    }

    if (FAILED(StringCchPrintfW(child_command, 2 * MAX_PATH,
            L"\"%s\" --logFilePrefix %s", game_path,
            worker ? L"vvg-worker-" : L"vvg-player-"))) {
        log_failure("child_command", ERROR_INSUFFICIENT_BUFFER);
        return 21;
    }

    if (worker) {
        if (FAILED(StringCchCopyW(ready_marker, MAX_PATH, g_root)) ||
                FAILED(StringCchCatW(ready_marker, MAX_PATH,
                    WORKER_READY_MARKER_FILE))) {
            return 5;
        }
        DeleteFileW(ready_marker);
        SetEnvironmentVariableW(WORKER_READY_MARKER_ENV, ready_marker);
    } else {
        SetEnvironmentVariableW(WORKER_READY_MARKER_ENV, 0);
    }

    job = CreateJobObjectW(0, 0);
    if (job == 0 || !configure_kill_job(job)) {
        log_failure("CreateJobObjectW", GetLastError());
        if (job != 0) {
            CloseHandle(job);
        }
        return 22;
    }

    ZeroMemory(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    if (worker) {
        if (FAILED(StringCchPrintfW(desktop_name, 96,
                L"VVGWorker_%lu", (unsigned long)GetCurrentProcessId())) ||
                FAILED(StringCchPrintfW(full_desktop_name, 128,
                    L"WinSta0\\%s", desktop_name))) {
            CloseHandle(job);
            return 5;
        }
        if (CreateDesktopW(desktop_name, 0, 0, 0, GENERIC_ALL, 0) == 0) {
            /* Fall back to the default desktop if CreateDesktop is denied. */
            log_failure("CreateDesktopW", GetLastError());
            startup.lpDesktop = 0;
        } else {
            startup.lpDesktop = full_desktop_name;
            SetEnvironmentVariableW(HIDDEN_DESKTOP_ENV, HIDDEN_DESKTOP_VALUE);
        }
    }

    if (!CreateProcessW(game_path, child_command, 0, 0, FALSE,
            CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP, 0, g_root,
            &startup, &process)) {
        log_failure("CreateProcessW", GetLastError());
        CloseHandle(job);
        return 22;
    }
    if (!AssignProcessToJobObject(job, process.hProcess)) {
        log_failure("AssignProcessToJobObject", GetLastError());
        TerminateProcess(process.hProcess, 23);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        CloseHandle(job);
        return 23;
    }
    if (ResumeThread(process.hThread) == (DWORD)-1) {
        log_failure("ResumeThread", GetLastError());
        TerminateProcess(process.hProcess, 24);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        CloseHandle(job);
        return 24;
    }
    CloseHandle(process.hThread);
    process.hThread = 0;

    if (worker) {
        ready_state = wait_for_worker_ready(process.hProcess, stop_event,
            ready_marker);
        if (ready_state <= 0) {
            if (WaitForSingleObject(process.hProcess, 0) == WAIT_OBJECT_0 &&
                    GetExitCodeProcess(process.hProcess, &exit_code)) {
                result = (int)exit_code;
            } else {
                result = 25;
            }
            goto cleanup;
        }
        if (!publish_ready_marker(ready_marker)) {
            log_failure("publish_ready_marker", GetLastError());
            result = 25;
            goto cleanup;
        }
    }

    wait_state = WaitForSingleObject(process.hProcess, INFINITE);
    if (wait_state == WAIT_OBJECT_0) {
        if (!GetExitCodeProcess(process.hProcess, &exit_code)) {
            exit_code = 26;
        }
        result = (int)exit_code;
    } else if (wait_state == WAIT_FAILED) {
        log_failure("WaitForSingleObject(client)", GetLastError());
        result = 26;
    } else if (stop_event != 0 &&
            wait_state == WAIT_OBJECT_0 + 1) {
        result = 0;
    }

cleanup:
    if (stop_event != 0 &&
            WaitForSingleObject(stop_event, 0) == WAIT_OBJECT_0 &&
            WaitForSingleObject(process.hProcess, 0) == WAIT_TIMEOUT) {
        TerminateJobObject(job, ERROR_PROCESS_ABORTED);
        WaitForSingleObject(process.hProcess, STOP_TIMEOUT_MS);
        result = 0;
    }
    if (process.hProcess != 0) {
        CloseHandle(process.hProcess);
    }
    CloseHandle(job);
    if (worker && ready_marker[0] != L'\0') {
        DeleteFileW(ready_marker);
    }
    return result;
}


int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous_instance,
        LPWSTR command_line, int show_command)
{
    WCHAR game_path[MAX_PATH];
    HANDLE stop_event = 0;
    HANDLE singleton = 0;
    DWORD stop_target = 0;
    int stop_state;
    BOOL worker = TRUE;
    int result;

    (void)instance;
    (void)previous_instance;
    (void)show_command;

    g_root[0] = L'\0';
    stop_state = parse_starter_stop_command(command_line, &stop_target);
    if (stop_state < 0) {
        return 29;
    }
    if (stop_state > 0) {
        return signal_starter_stop(stop_target);
    }
    if (lstrcmpiW(command_line, L"--player") == 0) {
        worker = FALSE;
    } else if (command_line != 0 && command_line[0] != L'\0' &&
            lstrcmpiW(command_line, L"--worker-only") != 0) {
        log_failure("unsupported_mode", ERROR_INVALID_PARAMETER);
        return 30;
    }

    if (!resolve_game_root(game_path, MAX_PATH)) {
        DWORD err = GetLastError();
        if (err == ERROR_SUCCESS) {
            err = ERROR_FILE_NOT_FOUND;
        }
        log_failure("resolve_game_root", err);
        return 4;
    }

    stop_event = create_starter_stop_event();
    if (stop_event == 0) {
        log_failure("CreateEventW", GetLastError());
        return 29;
    }

    if (worker) {
        singleton = CreateMutexW(0, TRUE, WORKER_MUTEX_NAME);
        if (singleton == 0) {
            log_failure("CreateMutexW", GetLastError());
            CloseHandle(stop_event);
            return 2;
        }
        if (GetLastError() == ERROR_ALREADY_EXISTS) {
            CloseHandle(singleton);
            CloseHandle(stop_event);
            return 3;
        }
    }

    result = launch_client(game_path, worker, stop_event);
    if (singleton != 0) {
        CloseHandle(singleton);
    }
    CloseHandle(stop_event);
    return result;
}
