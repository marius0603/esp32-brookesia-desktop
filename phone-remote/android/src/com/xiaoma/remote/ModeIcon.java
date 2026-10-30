package com.xiaoma.remote;
import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.Drawable;
/** Small vector symbols remain crisp at every Android display density. */
final class ModeIcon extends Drawable {
 final Paint paint=new Paint(3);final int kind,size;
 ModeIcon(Context context,int mode,int color){kind=mode;size=Math.round(24*context.getResources().getDisplayMetrics().density);paint.setColor(color);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(1.8f);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);}
 public int getIntrinsicWidth(){return size;}public int getIntrinsicHeight(){return size;}
 void line(Canvas c,float... points){Path p=new Path();p.moveTo(points[0],points[1]);for(int i=2;i<points.length;i+=2)p.lineTo(points[i],points[i+1]);c.drawPath(p,paint);}
 public void draw(Canvas c){c.save();c.translate(getBounds().left,getBounds().top);c.scale(getBounds().width()/24f,getBounds().height()/24f);
  if(kind==0){line(c,4,6,20,6,16,3);line(c,20,6,16,9);line(c,20,18,4,18,8,15);line(c,4,18,8,21);}
  else if(kind==1){line(c,3,6,7,6,17,18,21,18,18,15);line(c,21,18,18,21);line(c,3,18,7,18,17,6,21,6,18,3);line(c,21,6,18,9);}
  else{line(c,8,5,18,5,21,8,21,13);line(c,17,2,20,5,17,8);line(c,16,19,6,19,3,16,3,11);line(c,7,16,4,19,7,22);line(c,11,10,13,9,13,15);}
  c.restore();}
 public void setAlpha(int alpha){paint.setAlpha(alpha);}public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);}public int getOpacity(){return PixelFormat.TRANSLUCENT;}
}
