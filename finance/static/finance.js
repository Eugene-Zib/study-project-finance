function myFunction() {
  var strGET = "/check?username="+document.check.username.value;
  $.get(strGET, "get",
  function(data) {
    if (data.check === false) {
      alert(data.message);
    } else {
      return true;
    }
  });
  alertTaken();
}

function alertTaken() {
  alert("wow");
}

function buy(id) {
  document.location = "/buy?"+document.getElementById(id).value;
}

function sell(id) {
  window.location.href = "/sell?"+document.getElementById(id).value;
}
