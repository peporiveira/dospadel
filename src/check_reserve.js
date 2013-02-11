function check_reserve(date,time,name){
    var reserve = {
	date: date,
	time: time,
	name: name
    };
    var json_reserve = JSON.stringiy(reserve);
    alert(json_reserve);

}
check_reserve("hola","mundo","cruel");