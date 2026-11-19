$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$form = New-Object System.Windows.Forms.Form
$form.Text = 'VRAE - 手机扫码配对 / Reviewer MFA'
$form.Width = 650
$form.Height = if ($request.mode -eq 'pairing') { 650 } else { 335 }
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.ShowInTaskbar = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Left = 20
$label.Top = 20
$label.Width = 590
$label.Height = 85
if ($request.mode -eq 'pairing') {
    $label.Text = '请打开你自己手机上的 Microsoft Authenticator：点 + → 其他账户 → 扫描下方二维码。添加后的名称应为 VRAE Windows Reviewer。不要在聊天发送二维码、密钥或验证码。'
} else {
    $label.Text = 'Windows 账户密码已验证。请填写手机 Authenticator 中 VRAE Windows Reviewer 这一条目的当前六位验证码（不是短信码或 Microsoft 账户验证码）。'
}
if ($request.account_label) { $label.Text = $label.Text.Replace('VRAE Windows Reviewer',$request.account_label) }
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
    $help.Text = "左侧就是要用手机扫描的二维码。`r`n`r`n扫描后，手机应出现 VRAE Windows Reviewer，以及每30秒变化的六位数字。看到后再勾选下方确认框。`r`n`r`n电脑时间：" + $request.utc_display + "`r`n手机日期和时间请设为自动。"
    if ($request.account_label) { $help.Text = $help.Text.Replace('VRAE Windows Reviewer',$request.account_label) }
    $form.Controls.Add($help)
}

$ok = New-Object System.Windows.Forms.Button
$ok.Left = 275
$ok.Top = if ($request.mode -eq 'pairing') { 535 } else { 205 }
$ok.Width = 210
$ok.Height = 35
$ok.Text = if ($request.mode -eq 'pairing') { '已完成手机扫码，继续' } else { '验证当前手机验证码' }
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
if ($request.mode -ne 'pairing') {
    $form.AcceptButton = $ok
} else {
    $ok.Enabled = $false
    $confirmation = New-Object System.Windows.Forms.CheckBox
    $confirmation.Left = 20
    $confirmation.Top = 465
    $confirmation.Width = 590
    $confirmation.Height = 45
    $confirmation.Text = '我已用手机扫描此二维码，手机已显示 VRAE Windows Reviewer 的六位验证码'
    if ($request.account_label) { $confirmation.Text = $confirmation.Text.Replace('VRAE Windows Reviewer',$request.account_label) }
    $confirmation.Add_CheckedChanged({ $ok.Enabled = $confirmation.Checked })
    $form.Controls.Add($confirmation)
}
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class VraePairingWindow { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }'
$form.Add_Shown({ [void][VraePairingWindow]::ShowWindow($form.Handle,9); [void][VraePairingWindow]::SetForegroundWindow($form.Handle); $form.Activate(); $form.BringToFront() })
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
