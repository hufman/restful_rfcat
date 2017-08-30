var onSSE = function(e) {
	pieces = e.data.split('=');
	if (pieces.length == 2) {
		var device = pieces[0];
		var state = pieces[1];
		var text = document.getElementById(device + "-state");
		if (text) {
			text.innerHTML = state;
		}
	}
};

window.addEventListener('load', function() {
	if (window.EventSource) {
		sse = new EventSource('stream');
		sse.addEventListener('message', onSSE);
	}
});
