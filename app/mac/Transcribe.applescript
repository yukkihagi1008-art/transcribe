-- Transcribe.app のソース（install.command が osacompile でビルドする）。
-- ファイルをドラッグ&ドロップすると transcribe_only.py を実行する。
-- ダブルクリックした場合は YouTube URL を貼り付けるダイアログを出す。
-- scripts/ は install.command がこのアプリの Contents/Resources/scripts/ に
-- コピーするため、アプリはどこに移動してもそのまま動く（自己完結）。

on _run(inputArg)
	set appResources to (POSIX path of (path to me)) & "Contents/Resources/"
	set scriptsPath to appResources & "scripts/transcribe_only.py"

	display notification "処理中です。しばらくお待ちください…" with title "Transcribe"

	try
		set shellCmd to "export PATH=\"/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH\"; " & ¬
			"python3 " & quoted form of scriptsPath & " " & inputArg & " 2>&1 | tail -n 50"
		do shell script shellCmd
		display notification "文字起こしが完了しました" with title "Transcribe"
		do shell script "open " & quoted form of (appResources & "output")
	on error errMsg
		display alert "文字起こしでエラーが発生しました" message errMsg as critical
	end try
end _run

on open theFiles
	set fileArgs to ""
	repeat with f in theFiles
		set fileArgs to fileArgs & " " & quoted form of (POSIX path of f)
	end repeat
	my _run(fileArgs)
end open

on run
	set theURL to text returned of (display dialog "音声/動画ファイルはこのアプリにドラッグ&ドロップしてください。" & return & return & "YouTube URLの場合はここに貼り付けてOKを押してください。" default answer "" buttons {"キャンセル", "OK"} default button "OK" with title "Transcribe")
	if theURL is not "" then
		my _run(quoted form of theURL)
	end if
end run
