// This file is subject to the terms and conditions defined
// in file 'LICENSE', which is part of this source code package.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;

namespace DepotDownloader
{
    static class RheniumProtocol
    {
        static readonly TextWriter ProtocolOutput = Console.Out;
        public static bool Enabled { get; private set; }

        static void Emit(object value)
        {
            ProtocolOutput.WriteLine(JsonSerializer.Serialize(value));
            ProtocolOutput.Flush();
        }

        public static void EmitChallenge(string uri)
        {
            Emit(new { type = "challenge", uri });
        }

        static JsonElement Required(JsonElement root, string name)
        {
            if (!root.TryGetProperty(name, out var value))
                throw new InvalidDataException($"missing request field: {name}");
            return value;
        }

        static void LoadSession(JsonElement request, out string principal)
        {
            principal = Required(request, "principal").GetString();
            var session = Required(request, "session");
            var refreshToken = Required(session, "refreshToken").GetString();
            AccountSettingsStore.Instance.LoginTokens[principal] = refreshToken;
            if (session.TryGetProperty("guardData", out var guard) && !string.IsNullOrWhiteSpace(guard.GetString()))
                AccountSettingsStore.Instance.GuardData[principal] = guard.GetString();
        }

        static object SessionResult(string principal)
        {
            AccountSettingsStore.Instance.LoginTokens.TryGetValue(principal, out var refreshToken);
            AccountSettingsStore.Instance.GuardData.TryGetValue(principal, out var guardData);
            if (string.IsNullOrWhiteSpace(refreshToken))
                throw new InvalidDataException("Steam did not return a persistent refresh token");
            return new
            {
                type = "result",
                value = new { principal, refreshToken, guardData = guardData ?? "" }
            };
        }

        static void ClearStoredSession()
        {
            AccountSettingsStore.Instance.LoginTokens.Clear();
            AccountSettingsStore.Instance.GuardData.Clear();
            AccountSettingsStore.Save();
        }

        static async Task<object> Login()
        {
            await Task.CompletedTask;
            ContentDownloader.Config = new DownloadConfig
            {
                RememberPassword = true,
                UseQrCode = true,
                LoginID = 0x52484E // RHN
            };
            if (!ContentDownloader.InitializeSteam3(null, null))
                throw new InvalidDataException("Steam QR login failed");
            var principal = AccountSettingsStore.Instance.LoginTokens.Keys.Single();
            var result = SessionResult(principal);
            ContentDownloader.ShutdownSteam3();
            return result;
        }

        static async Task<object> Validate(JsonElement request)
        {
            LoadSession(request, out var principal);
            ContentDownloader.Config = new DownloadConfig
            {
                RememberPassword = true,
                LoginID = 0x52484E
            };
            if (!ContentDownloader.InitializeSteam3(principal, null))
                throw new InvalidDataException("stored Steam session is invalid or revoked");
            var result = SessionResult(principal);
            ContentDownloader.ShutdownSteam3();
            await Task.CompletedTask;
            return result;
        }

        static async Task<object> Acquire(JsonElement request)
        {
            LoadSession(request, out var principal);
            var source = Required(request, "source");
            var destination = Required(request, "destination").GetString();
            var appId = Required(source, "appId").GetUInt32();
            var depots = new List<(uint, ulong)>();
            foreach (var depot in Required(source, "depots").EnumerateArray())
                depots.Add((Required(depot, "id").GetUInt32(), ulong.Parse(Required(depot, "manifest").GetString())));
            ContentDownloader.Config = new DownloadConfig
            {
                RememberPassword = true,
                VerifyAll = true,
                InstallDirectory = destination,
                MaxDownloads = 8,
                LoginID = 0x52484E
            };
            if (!ContentDownloader.InitializeSteam3(principal, null))
                throw new InvalidDataException("stored Steam session is invalid or revoked");
            Emit(new { type = "progress", value = 5, phase = "Steam session validated" });
            await ContentDownloader.DownloadAppAsync(
                appId,
                depots,
                "public",
                source.TryGetProperty("os", out var os) ? os.GetString() : null,
                null,
                null,
                false,
                false
            ).ConfigureAwait(false);
            Emit(new { type = "progress", value = 100, phase = "Pinned depots acquired" });
            var result = SessionResult(principal);
            ContentDownloader.ShutdownSteam3();
            return result;
        }

        public static async Task<int> Run()
        {
            Enabled = true;
            try
            {
                var line = await Console.In.ReadLineAsync().ConfigureAwait(false);
                using var document = JsonDocument.Parse(line ?? throw new InvalidDataException("missing request"));
                var request = document.RootElement;
                var command = Required(request, "command").GetString();
                // Keep the protocol stream machine-readable; upstream diagnostics stay on stderr.
                Console.SetOut(TextWriter.Null);
                var result = command switch
                {
                    "login" => await Login().ConfigureAwait(false),
                    "validate" => await Validate(request).ConfigureAwait(false),
                    "acquire" => await Acquire(request).ConfigureAwait(false),
                    _ => throw new InvalidDataException($"unsupported command: {command}")
                };
                Emit(result);
                return 0;
            }
            catch (Exception error)
            {
                Emit(new { type = "error", message = error.Message });
                return 1;
            }
            finally
            {
                try { ClearStoredSession(); } catch { }
            }
        }
    }
}
