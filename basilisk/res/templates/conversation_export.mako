<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<title>${conversation.title or _("Conversation") | h}</title>
	<style>
		body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fff; }
		article { margin-bottom: 2rem; border-radius: 6px; padding: 1rem 1.25rem; }
		article.user { background: #f0f4ff; }
		article.assistant { background: #f6faf3; }
		.meta { font-size: 0.8rem; color: #666; margin-top: 0.5rem; }
		pre { background: #f4f4f4; padding: 0.75rem; border-radius: 4px; overflow-x: auto; }
		code { font-family: monospace; }
		@media (prefers-color-scheme: dark) {
			body { background: #1a1a1a; color: #e8e8e8; }
			article.user { background: #1e2a40; }
			article.assistant { background: #1a2d1a; }
			.meta { color: #aaa; }
			pre { background: #2a2a2a; }
		}
	</style>
</head>
<body>
<header>
	<h1>${conversation.title or _("Conversation") | h}</h1>
	% if profile:
	<p class="meta">${_("Profile")}: ${profile.name | h}</p>
	% endif
</header>
<main role="log" aria-label="${_('Conversation history')}">
% for block in conversation.messages:
	<article class="user" aria-label="${_('User message')}">
		<div>${block.request.content | h}</div>
		% if block.request.attachments:
		% for att in block.request.attachments:
		<%
			mime = att.mime_type or "application/octet-stream"
			is_image = mime.startswith("image/")
			b64 = att.encoded_data if hasattr(att, "encoded_data") else ""
		%>
		% if is_image:
		<img src="data:${mime};base64,${b64}" alt="${att.name | h}" style="max-width:100%">
		% else:
		<a href="#" onclick="downloadAttachment('${b64}','${att.name | h}','${mime}');return false">${_("Download")} ${att.name | h}</a>
		% endif
		% endfor
		% endif
	</article>
	% if block.response:
	<article class="assistant" aria-label="${_('Assistant message')}">
		<div>${block.response.content | h}</div>
		<p class="meta">
			${block.model.name | h} &mdash;
			<time datetime="${block.created_at.isoformat()}">${block.created_at.strftime('%Y-%m-%d %H:%M')}</time>
		</p>
	</article>
	% endif
% endfor
</main>
<script>
function downloadAttachment(b64, filename, mime) {
	const bytes = atob(b64);
	const arr = new Uint8Array(bytes.length);
	for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
	const blob = new Blob([arr], {type: mime});
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	a.download = filename;
	a.click();
}
</script>
</body>
</html>
