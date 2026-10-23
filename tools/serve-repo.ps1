# Serves dist\local\repo (from tools/build_repo.py) at http://localhost:8765/
# so Kodi on this computer can install and update Backlot. Close the window to stop.
$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\dist\local\repo"))
$prefix = "http://localhost:8765/"
$types = @{ ".xml" = "text/xml"; ".md5" = "text/plain"; ".zip" = "application/zip"; ".png" = "image/png"; ".jpg" = "image/jpeg" }

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add($prefix)
try { $listener.Start() } catch {
    Write-Host "Couldn't start the server on $prefix. Is it already running in another window?" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
Write-Host "Backlot repository running at $prefix" -ForegroundColor Green
Write-Host "Serving $root"
Write-Host "Leave this window open while Kodi installs or updates Backlot."
while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $res = $ctx.Response
    try {
        $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/')) -replace '/', '\'
        $path = [IO.Path]::GetFullPath((Join-Path $root $rel))
        if ($path.StartsWith($root) -and (Test-Path $path -PathType Leaf)) {
            $bytes = [IO.File]::ReadAllBytes($path)
            $ext = [IO.Path]::GetExtension($path).ToLower()
            $res.ContentType = $(if ($types.ContainsKey($ext)) { $types[$ext] } else { "application/octet-stream" })
            $res.ContentLength64 = $bytes.Length
            # Kodi checks each file with HEAD before downloading it: headers only, no body
            if ($ctx.Request.HttpMethod -ne "HEAD") {
                try { $res.OutputStream.Write($bytes, 0, $bytes.Length) } catch { }  # Kodi hung up early; harmless
                Write-Host ("200  /" + ($rel -replace '\\', '/'))
            }
        } else {
            $res.StatusCode = 404
            Write-Host ("404  /" + ($rel -replace '\\', '/')) -ForegroundColor Yellow
        }
    } catch {
        $res.StatusCode = 500
        Write-Host $_ -ForegroundColor Red
    } finally {
        try { $res.Close() } catch { }
    }
}
