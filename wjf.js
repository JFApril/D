var a=document.getElementsByName("details-control")
for(i=0;i<a.length;i++){
a[i].click()
}
var b=document.getElementsByName("verakName")
var j=1
do{
    b[j].value="Wang Jianfeng"  
    j+=4
}while(j<b.length)
