function refreshHistory() {
	$.get('/history', function(data) {
		$('#historyListView').html(data);
		$('#historyListView').listview('refresh');
	});
}
function control(action) {
	var url = "/control/" + action;
	$.post(url, function(data) {
		if (data !== "") {
			if (data === "OK") {
				if (action === "stop") {
					$('#title').html('N/A');
					$('#duration').html('N/A');
					$('#formatSelect').html('');
					$('#relatedVideo').html('');
				}
				showMessage("");
			} else {
				showMessage(data);
			}
		}
	});
}
function deleteHistory(id) {
	var url = "/delete/" + id;
	$.post(url, function(data) {
		refreshHistory();
	});
}
function clearHistory() {
	var url = "/clear";
	$.post(url, function(data) {
		refreshHistory();
	});
}
function showMessage(message, timeout) {
	timeout = typeof timeout !== 'undefined' ? timeout : 1500;
	if (message === "") {
		$(".ctlbtn").removeClass('ui-btn-active');
		return;
	}
	$("#message").html(message);
	$("#message").popup('open');
	setTimeout(function() {
		$("#message").popup('close');
		$(".ctlbtn").removeClass('ui-btn-active');
	}, timeout);
}
function updateProgress() {
	$.get('/progress', function(data) {
		if(data['title'] !== $('#title').html()) {
			console.log("Refresh page");
			window.location = "/";
		}
		$('#title').html(data['title']);
		$('#duration').html(data['duration']);
		$('#progressbar').val(data['progress']);
		$('#progressbar').slider('refresh');
	});
}
function getProgress() {
	updateProgress();
	$("#progressbar").on('slidestop', function(event) {
		var gotoValue = $("#progressbar").val();
		console.log(gotoValue);
		$.post('/goto/' + gotoValue, function(data) {
			if (data !== 'OK') {
				showMessage("Nothing to do", 1500);
			}
		});
	});
	setInterval(function() {
		updateProgress();
	}, 5000);
}
function goAndRedirect(go, redirect) {
	$.get(go, function(data) {
		window.location = redirect;
	});
}
function initHotkeys() {
	textAcceptingInputTypes = ["text", "password", "number", "email", "url", "range", "date", "month", "week", "time", "datetime", "datetime-local", "search", "color"];
	$(document).keypress(function(e) {
		// Don't fire in text-accepting inputs that we didn't directly bind to
		if ( this !== e.target && (/textarea|select/i.test( e.target.nodeName ) ||
			jQuery.inArray(e.target.type, textAcceptingInputTypes) > -1 ) ) {
			return;
		}
		if (e.keyCode == '32' || e.keyCode == '112') {
			control('pause');
		} else if (e.keyCode == '113') {
			control('stop');
		} else if (e.keyCode == '43' || e.keyCode == '61') {
			control('volup');
		} else if (e.keyCode == '45' || e.keyCode == '95') {
			control('voldown');
		}
	});
}
