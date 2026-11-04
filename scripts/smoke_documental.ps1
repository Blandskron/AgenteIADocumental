param(
    [Parameter(Mandatory)][PSCredential]$Credential
)

$ErrorActionPreference = 'Stop'
$loginBody = @{
    username = $Credential.UserName
    password = $Credential.GetNetworkCredential().Password
} | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/api/users/login/' -ContentType 'application/json' -Body $loginBody -TimeoutSec 30
$headers = @{ Authorization = "Bearer $($login.access)" }

$filename = "blandskron-demo-$([guid]::NewGuid().ToString('N')).txt"
$fixture = Join-Path ([IO.Path]::GetTempPath()) $filename
$question = '¿Cuántos días dura el contrato de prueba?'
try {
    Set-Content -LiteralPath $fixture -Value 'El contrato sintético de demostración tiene una duración de 97 días.' -Encoding utf8
    $upload = Invoke-RestMethod -Method Post -Uri 'http://localhost:8003/api/v1/documents/upload' -Headers $headers -Form @{
        file = Get-Item -LiteralPath $fixture
        process = 'true'
    } -TimeoutSec 300
    if ($upload.status -ne 'PROCESSED') {
        throw "La ingesta devolvió el estado $($upload.status)."
    }

    $search = Invoke-RestMethod -Uri "http://localhost:8004/api/v1/documents/search?q=$filename" -Headers $headers -TimeoutSec 30
    if ($upload.document_id -notin $search.items.document_id) {
        throw 'La búsqueda no encontró el documento de prueba.'
    }

    $chatBody = @{ question = $question; document_ids = @($upload.document_id) } | ConvertTo-Json
    $chat = Invoke-RestMethod -Method Post -Uri 'http://localhost:8002/api/v1/chat/ask' -Headers $headers -ContentType 'application/json' -Body $chatBody -TimeoutSec 300
    if ($chat.answer -notmatch '\b97\b' -or $upload.document_id -notin $chat.sources.document_id) {
        throw 'El chat no devolvió la respuesta esperada con su fuente documental.'
    }

    $exportBody = @{
        title = 'Prueba sintética de Blandskron Documental'
        question = $question
        answer = $chat.answer
        sources = @($chat.sources)
    } | ConvertTo-Json -Depth 8
    $export = Invoke-RestMethod -Method Post -Uri 'http://localhost:8016/api/v1/exports/chat-message/pdf' -Headers $headers -ContentType 'application/json' -Body $exportBody -TimeoutSec 30
    $pdf = Invoke-WebRequest -Uri "http://localhost:8016/api/v1/exports/$($export.export_id)/download" -Headers $headers -TimeoutSec 30
    if ($pdf.Headers['Content-Type'] -notmatch 'application/pdf' -or $pdf.RawContentLength -eq 0) {
        throw 'La descarga no devolvió un PDF válido.'
    }

    "Flujo correcto. Documento $($upload.document_id), exportación $($export.export_id)."
} finally {
    if (Test-Path -LiteralPath $fixture) {
        Remove-Item -LiteralPath $fixture
    }
}
