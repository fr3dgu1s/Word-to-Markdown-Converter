using System;
using System.Threading;
using Microsoft.Identity.Client;
using Microsoft.InformationProtection;

namespace WordToMd.MipHelper;

/// <summary>
/// Bridges the MIP File SDK <see cref="IAuthDelegate"/> to MSAL.
/// The SDK calls <see cref="AcquireToken"/> synchronously; we delegate to
/// <see cref="MipAuth.AcquireTokenAsync"/> and wait for the result.
/// </summary>
internal sealed class MipAuthDelegate : IAuthDelegate
{
    private readonly IPublicClientApplication _app;
    private readonly string? _userHint;

    public MipAuthDelegate(IPublicClientApplication app, string? userHint)
    {
        _app = app;
        _userHint = userHint;
    }

    public string AcquireToken(Identity identity, string authority, string resource, string claims)
    {
        // The MIP SDK passes a v1.0-style resource URI. Convert to a v2.0
        // ".default" scope for MSAL.
        var scope = resource.TrimEnd('/') + "/.default";
        var hint = string.IsNullOrWhiteSpace(identity?.Email) ? _userHint : identity!.Email;

        try
        {
            return MipAuth.AcquireTokenAsync(_app, new[] { scope }, hint, CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                $"MIP token acquisition failed for resource '{resource}': {ex.Message}", ex);
        }
    }
}

/// <summary>
/// Auto-accept consent prompts. The MIP SDK raises this when the engine
/// needs the user to acknowledge a tenant policy URL; for an unattended
/// CLI helper we treat it as accepted and let RMS enforce real
/// permissions on RemoveProtection.
/// </summary>
internal sealed class MipConsentDelegate : IConsentDelegate
{
    public Consent GetUserConsent(string url) => Consent.Accept;
}
