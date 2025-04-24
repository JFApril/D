//E-flow web test
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


//taobao test
var widget = id("com.taobao.taobao:id/count_down_timer_view_container").findOne(200);
if (widget) {
    // 长按控件的中心点
    longClick(widget.bounds().centerX(), widget.bounds().centerY());
    sleep(500); // 等待200毫秒
    
    // 获取控件左上角的坐标
    var px1 = widget.bounds().left;
    var py1 = widget.bounds().top;
    
    // 点击相对于控件左上角偏移的坐标
    click(px1 + 100, py1 - 244);
    sleep(200);
    id("com.taobao.taobao:id/uik_mdButtonDefaultPositive").findOne(200).click();
    toastLog("已删除倒计时");
} else {
    toastLog("未找到倒计时");  
}
