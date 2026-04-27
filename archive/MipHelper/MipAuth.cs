using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Identity.Client;
using Microsoft.Identity.Client.Broker;

namespace WordToMd.MipHelper;

/// <summary>
/// MSAL public-client builder + token acquisition strategy used by the
/// MIP helper. Configuration is read from environment variables that the
/// Python orchestrator exports from <c>.env</c>:
///
///   MIP_CLIENT_ID      - required, Azure AD app (public client)
///   MIP_TENANT_ID      - optional, default "organizations"
///   MIP_REDIRECT_URI   - optional, default "http://localhost"
///
/// Token acquisition order:
///   1. <see cref="IPublicClientApplication.AcquireTokenSilent"/> against
///      any cached account (broker-cached when WAM is available).
///   2. Integrated Windows Auth (domain-joined SSO).
///   3. Interactive auth via WAM broker, falling back to the system
///      browser when the broker is unavailable.
/// </summary>
internal static class MipAuth
{
    public const string GraphAuthority = "https://login.microsoftonline.com";

    // Microsoft Graph scopes used to resolve and download the file.
    public static readonly string[] GraphScopes =
    {
        "Files.Read.All",
        "Sites.Read.All",
    };

    // Resource used by the MIP File SDK's IAuthDelegate. The SDK passes a
    // resource URI; the helper appends "/.default" to form a v2.0 scope.
    public static readonly string MipResource = "https://syncservice.o365syncservice.com";

    public static IPublicClientApplication BuildClient()
    {
        var clientId = RequireEnv("MIP_CLIENT_ID");
        var tenantId = Env("MIP_TENANT_ID", "organizations");
        var redirect = Env("MIP_REDIRECT_URI", "http://localhost");

        var builder = PublicClientApplicationBuilder
            .Create(clientId)
            .WithAuthority($"{GraphAuthority}/{tenantId}")
            .WithRedirectUri(redirect);

        // WAM broker is preferred on Windows: it gives SSO with the signed-in
        // Windows account and handles MFA/Conditional Access transparently.
        try
        {
            var brokerOptions = new BrokerOptions(BrokerOptions.OperatingSystems.Windows)
            {
                Title = "Word-to-Markdown Converter",
            };
            builder = builder.WithBroker(brokerOptions);
        }
        catch
        {
            // Broker not available (older OS / missing dependency). Fall back
            // to system-browser interactive auth.
        }

        return builder.Build();
    }

    public static async Task<string> AcquireTokenAsync(
        IPublicClientApplication app,
        string[] scopes,
        string? userHint,
        CancellationToken ct)
    {
        // 1. Silent (cache / broker SSO).
        var accounts = await app.GetAccountsAsync().ConfigureAwait(false);
        IAccount? account = null;
        if (!string.IsNullOrWhiteSpace(userHint))
        {
            account = accounts.FirstOrDefault(a =>
                string.Equals(a.Username, userHint, StringComparison.OrdinalIgnoreCase));
        }
        account ??= accounts.FirstOrDefault() ?? PublicClientApplication.OperatingSystemAccount;

        try
        {
            var silent = await app.AcquireTokenSilent(scopes, account)
                .ExecuteAsync(ct)
                .ConfigureAwait(false);
            return silent.AccessToken;
        }
        catch (MsalUiRequiredException)
        {
            // Continue to next strategy.
        }
        catch (MsalServiceException)
        {
            // Continue to next strategy.
        }

        // 2. Integrated Windows Auth.
        if (!string.IsNullOrWhiteSpace(userHint))
        {
            try
            {
                var iwa = await app.AcquireTokenByIntegratedWindowsAuth(scopes)
                    .WithUsername(userHint)
                    .ExecuteAsync(ct)
                    .ConfigureAwait(false);
                return iwa.AccessToken;
            }
            catch
            {
                // Fall through to interactive.
            }
        }
        else
        {
            try
            {
                var iwa = await app.AcquireTokenByIntegratedWindowsAuth(scopes)
                    .ExecuteAsync(ct)
                    .ConfigureAwait(false);
                return iwa.AccessToken;
            }
            catch
            {
                // Fall through to interactive.
            }
        }

        // 3. Interactive (broker or system browser).
        var interactiveBuilder = app.AcquireTokenInteractive(scopes)
            .WithUseEmbeddedWebView(false);
        if (!string.IsNullOrWhiteSpace(userHint))
        {
            interactiveBuilder = interactiveBuilder.WithLoginHint(userHint);
        }
        var interactive = await interactiveBuilder
            .ExecuteAsync(ct)
            .ConfigureAwait(false);
        return interactive.AccessToken;
    }

    private static string RequireEnv(string name)
    {
        var value = Environment.GetEnvironmentVariable(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException(
                $"{name} is not set. Define it in .env (e.g. {name}=<your-app-client-id>) " +
                "before running the MIP helper.");
        }
        return value.Trim();
    }

    private static string Env(string name, string fallback)
    {
        var value = Environment.GetEnvironmentVariable(name);
        return string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();
    }
}
