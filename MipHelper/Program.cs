using System;
using System.CommandLine;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;

namespace WordToMd.MipHelper;

/// <summary>
/// Command-line MIP helper that the Python orchestrator invokes for
/// inspect / unprotect / protect operations on Office files.
///
/// Exit codes (kept stable for Python parsing):
///   0  success
///   10 file is not protected (inspect only)
///   20 access denied by Purview policy
///   30 protection could not be reapplied
///   99 generic helper failure
/// </summary>
public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        var inputOption = new Option<FileInfo>("--input")    { IsRequired = true };
        var outputOption = new Option<FileInfo>("--output")  { IsRequired = false };
        var metadataOption = new Option<FileInfo>("--metadata") { IsRequired = true };
        var userOption = new Option<string?>("--user")       { IsRequired = false };

        var inspect = new Command("inspect", "Inspect a file and write its sensitivity-label metadata to JSON.");
        inspect.AddOption(inputOption);
        inspect.AddOption(metadataOption);
        inspect.SetHandler((FileInfo input, FileInfo meta) =>
        {
            return RunInspect(input, meta);
        }, inputOption, metadataOption);

        var unprotect = new Command("unprotect", "Create a decrypted working copy if the user has rights.");
        unprotect.AddOption(inputOption);
        unprotect.AddOption(outputOption);
        unprotect.AddOption(metadataOption);
        unprotect.AddOption(userOption);
        unprotect.SetHandler((FileInfo input, FileInfo? output, FileInfo meta, string? user) =>
        {
            if (output == null) { Console.Error.WriteLine("--output is required for unprotect"); return Task.FromResult(99); }
            return RunUnprotect(input, output, meta, user);
        }, inputOption, outputOption, metadataOption, userOption);

        var protect = new Command("protect", "Reapply the originally captured label/protection to an edited file.");
        protect.AddOption(inputOption);
        protect.AddOption(outputOption);
        protect.AddOption(metadataOption);
        protect.AddOption(userOption);
        protect.SetHandler((FileInfo input, FileInfo? output, FileInfo meta, string? user) =>
        {
            if (output == null) { Console.Error.WriteLine("--output is required for protect"); return Task.FromResult(99); }
            return RunProtect(input, output, meta, user);
        }, inputOption, outputOption, metadataOption, userOption);

        var urlOption = new Option<string>("--url") { IsRequired = true };
        var fetchUnprotect = new Command("fetch-unprotect",
            "Fetch a protected SharePoint/OneDrive URL with user credentials and write a decrypted local copy.");
        fetchUnprotect.AddOption(urlOption);
        fetchUnprotect.AddOption(outputOption);
        fetchUnprotect.AddOption(userOption);
        fetchUnprotect.SetHandler((string url, FileInfo? output, string? user) =>
        {
            if (output == null) { Console.Error.WriteLine("--output is required for fetch-unprotect"); return Task.FromResult(99); }
            return RunFetchUnprotect(url, output, user);
        }, urlOption, outputOption, userOption);

        var root = new RootCommand("Word-to-Markdown MIP Helper");
        root.AddCommand(inspect);
        root.AddCommand(unprotect);
        root.AddCommand(protect);
        root.AddCommand(fetchUnprotect);

        return await root.InvokeAsync(args);
    }

    // -----------------------------------------------------------------------
    // inspect
    // -----------------------------------------------------------------------

    private static async Task<int> RunInspect(FileInfo input, FileInfo metadata)
    {
        try
        {
            // TODO (MIP SDK):
            //   1) Initialise IFileProfile / IFileEngine for the current user.
            //   2) Use IFileHandler.GetLabelAsync() / GetProtection() to read:
            //        - label id, label name, tenant id
            //        - protection descriptor (rights, owner, content id)
            //   3) Persist that descriptor to disk so 'protect' can rebuild it
            //      later via ProtectionDescriptorBuilder.CreateFromSerializedTemplate(...)
            //
            // The skeleton below writes a placeholder JSON so the Python
            // orchestrator can be wired and tested without the SDK calls.
            var isProtected = LooksProtectedHeuristic(input.FullName);

            var payload = new
            {
                is_protected = isProtected,
                label_id     = (string?)null,
                label_name   = (string?)null,
                tenant_id    = (string?)null,
                owner        = (string?)null,
                rights       = Array.Empty<string>(),
                source_path  = input.FullName,
            };

            await WriteJsonAsync(metadata, payload);
            return isProtected ? 0 : 10;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"inspect failed: {ex}");
            return 99;
        }
    }

    // -----------------------------------------------------------------------
    // unprotect
    // -----------------------------------------------------------------------

    private static async Task<int> RunUnprotect(FileInfo input, FileInfo output, FileInfo metadata, string? user)
    {
        try
        {
            // TODO (MIP SDK):
            //   1) Acquire delegated token for the user (MSAL public client).
            //   2) Build IFileProfile + IFileEngine bound to that user.
            //   3) Create IFileHandler for 'input' and call RemoveProtectionAsync().
            //   4) On UnauthorizedAccess / NoRights: return 20.
            //   5) On any other failure: write Console.Error and return 99.
            //
            // The placeholder below simply copies the file so the orchestrator
            // can be exercised end-to-end before the SDK calls are filled in.
            File.Copy(input.FullName, output.FullName, overwrite: true);
            await Task.CompletedTask;
            return 0;
        }
        catch (UnauthorizedAccessException uae)
        {
            Console.Error.WriteLine($"access denied: {uae.Message}");
            return 20;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"unprotect failed: {ex}");
            return 99;
        }
    }

    // -----------------------------------------------------------------------
    // protect
    // -----------------------------------------------------------------------

    private static async Task<int> RunProtect(FileInfo input, FileInfo output, FileInfo metadata, string? user)
    {
        try
        {
            // TODO (MIP SDK):
            //   1) Read metadata.json and rebuild ProtectionDescriptor +
            //      LabelingOptions (assignmentMethod = Auto/Standard).
            //   2) Acquire delegated token for the user.
            //   3) Open IFileHandler for 'input' and call SetLabelAsync()
            //      with the original label, plus SetProtectionAsync() if a
            //      custom descriptor was captured.
            //   4) CommitAsync() to 'output'.
            //   5) Return 30 if the user lacks export/protect rights.
            //   6) Return 20 if Purview denies the operation outright.
            //   7) Return 99 for any other helper failure.
            File.Copy(input.FullName, output.FullName, overwrite: true);
            await Task.CompletedTask;
            return 0;
        }
        catch (UnauthorizedAccessException uae)
        {
            Console.Error.WriteLine($"access denied: {uae.Message}");
            return 20;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"protect failed: {ex}");
            return 99;
        }
    }

    // -----------------------------------------------------------------------
    // fetch-unprotect (Graph 403 fallback path)
    // -----------------------------------------------------------------------

    private static Task<int> RunFetchUnprotect(string url, FileInfo output, string? user)
    {
        // TODO (MIP SDK):
        //   1) Acquire a delegated token for the user via MSAL public client
        //      (interactive or device-code) bound to the user's tenant.
        //   2) Use the SharePoint/OneDrive REST path that the Office desktop
        //      apps use: open the protected file stream with user creds and
        //      call IFileHandler.RemoveProtectionAsync() to materialise a
        //      decrypted copy at 'output'.
        //   3) Return:
        //        0  on success
        //       20  when Purview denies access (UnauthorizedAccessException)
        //       99  for any other failure
        Console.Error.WriteLine(
            "fetch-unprotect requires the MIP SDK plus an approved app registration. " +
            "Complete onboarding at https://aka.ms/mipsdkapponboarding and replace this stub.");
        Console.Error.WriteLine($"requested url: {url}");
        Console.Error.WriteLine($"requested output: {output.FullName}");
        Console.Error.WriteLine($"user: {user ?? "<none>"}");
        return Task.FromResult(99);
    }

    // -----------------------------------------------------------------------
    // helpers
    // -----------------------------------------------------------------------

    private static async Task WriteJsonAsync<T>(FileInfo target, T payload)
    {
        target.Directory?.Create();
        var json = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
        await File.WriteAllTextAsync(target.FullName, json);
    }

    private static bool LooksProtectedHeuristic(string path)
    {
        // Office files are ZIP archives. RMS-encrypted Office files are NOT
        // valid ZIPs, so a quick header check provides a useful default
        // until the MIP SDK calls are implemented.
        try
        {
            using var fs = File.OpenRead(path);
            Span<byte> header = stackalloc byte[4];
            int read = fs.Read(header);
            if (read < 4) return true;
            // ZIP local file header magic: 50 4B 03 04
            return !(header[0] == 0x50 && header[1] == 0x4B && header[2] == 0x03 && header[3] == 0x04);
        }
        catch
        {
            return true;
        }
    }
}
