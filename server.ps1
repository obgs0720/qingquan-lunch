$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add('http://localhost:8000/')
$listener.Start()
Write-Output '清泉中餐吧 running at http://localhost:8000/'

while ($listener.IsListening) {
  $context = $listener.GetContext()
  $path = [System.Uri]::UnescapeDataString($context.Request.Url.AbsolutePath)
  if ($path -eq '/') { $path = '/index.html' }
  if ($path -match '^/api/') {
    $context.Response.StatusCode = 404
    $bytes = [Text.Encoding]::UTF8.GetBytes('{"error":"SQLite API 尚未啟動，前端將使用離線模式"}')
    $context.Response.ContentType = 'application/json; charset=utf-8'
  } else {
    $file = Join-Path $root ($path.TrimStart('/').Replace('/', '\'))
    if (Test-Path -LiteralPath $file -PathType Leaf) {
      $bytes = [IO.File]::ReadAllBytes($file)
      $context.Response.StatusCode = 200
      $context.Response.ContentType = switch ([IO.Path]::GetExtension($file).ToLowerInvariant()) { '.html' { 'text/html; charset=utf-8' } '.css' { 'text/css; charset=utf-8' } '.js' { 'text/javascript; charset=utf-8' } default { 'application/octet-stream' } }
    } else {
      $context.Response.StatusCode = 404
      $bytes = [Text.Encoding]::UTF8.GetBytes('Not Found')
    }
  }
  $context.Response.ContentLength64 = $bytes.Length
  $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
  $context.Response.Close()
}
