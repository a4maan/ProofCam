package org.proofcam.benchmark;

import android.graphics.Bitmap;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.TreeSet;

/** Android resampling is bilinear: a distinct candidate from Python/Lanczos. */
public final class AndroidCandidate {
    public static final String NAME="android-qim12-bilinear-v1";
    private AndroidCandidate() {}
    static int[] pixels(Bitmap image) {
        int w=image.getWidth(),h=image.getHeight();
        if ((long)w*h>20000000 || w>16384 || h>16384) throw new IllegalArgumentException("Image too large");
        int[] data=new int[w*h]; image.getPixels(data,0,w,0,0,w,h); return data;
    }
    public static Bitmap embed(Bitmap source,String id) {
        int w=source.getWidth(),h=source.getHeight();
        return Bitmap.createBitmap(DctCore.embed(pixels(source),w,h,id),w,h,Bitmap.Config.ARGB_8888);
    }
    static int[] border(Bitmap image) {
        int w=image.getWidth(),h=image.getHeight(); int[] p=pixels(image);int color=p[0];
        int left=w,top=h,right=-1,bottom=-1;
        for(int y=0;y<h;y++) for(int x=0;x<w;x++) if(p[y*w+x]!=color) {
            left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
        }
        if(right<left || (long)(right-left+1)*(bottom-top+1)<(long)w*h/4
                || (left==0 && top==0 && right==w-1 && bottom==h-1)) return null;
        return new int[]{left,top,right+1,bottom+1};
    }
    public static JSONObject extract(Bitmap input) throws Exception {
        JSONArray attempts=new JSONArray();TreeSet<String> ids=new TreeSet<>();
        region(input,"whole",new int[]{0,0,input.getWidth(),input.getHeight()},attempts,ids);
        int[] box=border(input);
        if(box!=null) {
            Bitmap crop=Bitmap.createBitmap(input,box[0],box[1],box[2]-box[0],box[3]-box[1]);
            region(crop,"uniform_border_trim",box,attempts,ids);if(crop!=input)crop.recycle();
        }
        if(attempts.length()>4) throw new IllegalStateException("Search budget exceeded");
        return new JSONObject().put("candidate",NAME).put("decoded_ids",new JSONArray(ids))
                .put("attempts",attempts).put("search_complete",true);
    }
    static void region(Bitmap image,String name,int[] box,JSONArray attempts,TreeSet<String> ids) throws Exception {
        view(image,name+":native",box,attempts,ids);
        int edge=Math.max(image.getWidth(),image.getHeight());
        if(edge!=1024) {
            Bitmap scaled=Bitmap.createScaledBitmap(image,Math.max(1,(int)Math.rint(image.getWidth()*1024.0/edge)),
                    Math.max(1,(int)Math.rint(image.getHeight()*1024.0/edge)),true);
            view(scaled,name+":edge1024",box,attempts,ids);if(scaled!=image)scaled.recycle();
        }
    }
    static void view(Bitmap image,String name,int[] box,JSONArray attempts,TreeSet<String> ids) throws Exception {
        JSONObject row=new JSONObject().put("geometry",name).put("width",image.getWidth()).put("height",image.getHeight());
        JSONArray rect=new JSONArray();for(int value:box)rect.put(value);row.put("rectangle",rect);
        try {
            String id=DctCore.extract(pixels(image),image.getWidth(),image.getHeight());
            row.put("status","searched").put("decoded_id",id==null?JSONObject.NULL:id);if(id!=null)ids.add(id);
        } catch(IllegalArgumentException error) {row.put("status","insufficient_capacity").put("decoded_id",JSONObject.NULL);}
        attempts.put(row);
    }
}
