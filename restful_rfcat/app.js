var sse_startup = false;

var onSSEConnect = function(e) {
	// surpress animations during the initial SSE sync
	sse_startup = true;
	window.setTimeout(function() {
		sse_startup = false;
	}, 2000);
}

var onSSE = function(e) {
	pieces = e.data.split('=');
	if (pieces.length == 2) {
		var device = pieces[0];
		var state = pieces[1];
		var text = document.getElementById(device + "-state");
		if (text) {
			text.innerHTML = state;
			var clearFunction = function() {
				text.classList.remove('changed')
				text.removeEventListener('animationend', clearFunction);
				clearTimeout(timer);
			};
			if (!sse_startup) {
				text.classList.add('changed');
				// if we have animation support, clear at the end
				text.addEventListener('animationend', clearFunction);
				// if we don't, clear the listener anyways
				var timer = window.setTimeout(clearFunction, 2000);
			}
		}
	}
};

window.addEventListener('load', function() {
	if (window.EventSource) {
		sse = new EventSource('stream');
		sse.addEventListener('open', onSSEConnect);
		sse.addEventListener('message', onSSE);
	}
});
