$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$form = New-Object System.Windows.Forms.Form
$form.Text = 'VRAE - local Reviewer MFA'
$form.Width = 650
$form.Height = if ($request.mode -eq 'pairing') { 650 } else { 335 }
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Left = 20
$label.Top = 20
$label.Width = 590
$label.Height = 85
if ($request.mode -eq 'pairing') {
    $label.Text = 'On your phone: Microsoft Authenticator -> + -> Other account -> Scan QR code below. Account: VRAE Windows Reviewer. Or enter the key manually. Keep both private; never send them in chat.'
} else {
    $label.Text = 'Enter the current 6-digit Microsoft Authenticator code for VRAE Windows Reviewer. Windows password verification has already succeeded. A reused code is rejected.'
}
$form.Controls.Add($label)
$input = New-Object System.Windows.Forms.TextBox
$input.Left = 20
$input.Top = 115
$input.Width = 590
$input.Font = New-Object System.Drawing.Font('Consolas',16)
if ($request.mode -eq 'pairing') {
    $input.ReadOnly = $true
    $input.Text = $request.seed
} else {
    $input.MaxLength = 6
    $input.UseSystemPasswordChar = $true
}
$form.Controls.Add($input)
if ($request.mode -eq 'pairing') {
    $bytes = [Convert]::FromBase64String($request.qr_png)
    $stream = New-Object System.IO.MemoryStream(,$bytes)
    $qr = New-Object System.Windows.Forms.PictureBox
    $qr.Left = 20
    $qr.Top = 170
    $qr.Width = 280
    $qr.Height = 280
    $qr.SizeMode = 'Zoom'
    $qr.Image = [System.Drawing.Image]::FromStream($stream)
    $form.Controls.Add($qr)
    $help = New-Object System.Windows.Forms.Label
    $help.Left = 320
    $help.Top = 190
    $help.Width = 280
    $help.Height = 240
    $help.Text = "Scan this with Authenticator on your own phone. Confirm it displays a changing six-digit code for VRAE Windows Reviewer. Then continue on this PC.`r`n`r`nPC time: " + $request.utc_display + "`r`nPhone automatic date and time must match."
    $form.Controls.Add($help)
}

$ok = New-Object System.Windows.Forms.Button
$ok.Left = 275
$ok.Top = if ($request.mode -eq 'pairing') { 535 } else { 205 }
$ok.Width = 210
$ok.Height = 35
$ok.Text = if ($request.mode -eq 'pairing') { 'Key added to phone, continue' } else { 'Verify this code' }
$ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($ok)
$cancel = New-Object System.Windows.Forms.Button
$cancel.Left = 500
$cancel.Top = if ($request.mode -eq 'pairing') { 535 } else { 205 }
$cancel.Width = 110
$cancel.Height = 35
$cancel.Text = 'Cancel'
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($cancel)
$form.AcceptButton = $ok
$form.CancelButton = $cancel
$result = $form.ShowDialog()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
    '{"cancelled":true}'
} elseif ($request.mode -eq 'pairing') {
    '{"paired_key_entered":true}'
} elseif ($input.Text -cmatch '^[0-9]{6}$') {
    @{code=$input.Text} | ConvertTo-Json -Compress
} else {
    '{"invalid_code":true}'
}
$input.Clear()
if ($null -ne $qr) { $qr.Image.Dispose(); $qr.Dispose(); $stream.Dispose(); [Array]::Clear($bytes,0,$bytes.Length) }
$form.Dispose()
