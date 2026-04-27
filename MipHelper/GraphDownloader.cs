using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace WordToMd.MipHelper;

/// <summary>
/// Minimal Microsoft Graph client used by fetch-unprotect to resolve a
/// SharePoint/OneDrive sharing URL to a driveItem and stream its bytes.
/// </summary>
internal static class GraphDownloader
{
    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromSeconds(90),
    };

    /// <summary>
    /// Resolves a SharePoint/OneDrive URL via <c>/shares/{encoded-id}/driveItem</c>
    /// and downloads the binary content to <paramref name="destination"/>.
    /// </summary>
    public static async Task DownloadByUrlAsync(
        string accessToken,
        string url,
        string destination,
        CancellationToken ct)
    {
        var encoded = EncodeSharingUrl(url);

        // 1. Resolve URL -> driveItem (returns id, parentReference.driveId, name).
        using var resolveReq = new HttpRequestMessage(
            HttpMethod.Get,
            $"https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem?$select=id,name,parentReference");
        resolveReq.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        using var resolveResp = await Http.SendAsync(resolveReq, ct).ConfigureAwait(false);
        var resolveBody = await resolveResp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
        if (!resolveResp.IsSuccessStatusCode)
        {
            throw new HttpRequestException(
                $"Graph /shares lookup failed ({(int)resolveResp.StatusCode}): {resolveBody}");
        }

        using var doc = JsonDocument.Parse(resolveBody);
        var root = doc.RootElement;
        var itemId = root.GetProperty("id").GetString()
            ?? throw new InvalidOperationException("driveItem id missing in Graph response.");
        var driveId = root.GetProperty("parentReference").GetProperty("driveId").GetString()
            ?? throw new InvalidOperationException("driveItem parentReference.driveId missing in Graph response.");

        // 2. Stream the file bytes.
        using var contentReq = new HttpRequestMessage(
            HttpMethod.Get,
            $"https://graph.microsoft.com/v1.0/drives/{driveId}/items/{itemId}/content");
        contentReq.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        using var contentResp = await Http.SendAsync(
            contentReq, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
        if (!contentResp.IsSuccessStatusCode)
        {
            var errBody = await contentResp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            throw new HttpRequestException(
                $"Graph /content download failed ({(int)contentResp.StatusCode}): {errBody}");
        }

        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
        await using var src = await contentResp.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
        await using var dst = File.Create(destination);
        await src.CopyToAsync(dst, ct).ConfigureAwait(false);
    }

    /// <summary>
    /// Encodes a sharing URL per the Graph spec:
    ///   "u!" + base64-url(no-padding) of the UTF-8 URL bytes.
    /// </summary>
    public static string EncodeSharingUrl(string url)
    {
        var bytes = Encoding.UTF8.GetBytes(url);
        var b64 = Convert.ToBase64String(bytes)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');
        return "u!" + b64;
    }
}
