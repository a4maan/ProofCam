package org.proofcam.benchmark;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.os.Debug;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.graphics.ColorSpace;
import android.net.Uri;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.nio.ByteBuffer;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;

/** Offline research UI. No camera, network, registration, or certification features. */
public final class MainActivity extends Activity {
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final ArrayList<Button> actions=new ArrayList<>();
    private TextView status;private ImageView preview;private CheckBox attest;private EditText mediaRectangle;
    private Bitmap source;private byte[] marked;private String expected;private JSONObject report=new JSONObject();
    private static final int PHOTO=10,SCREEN=11,SAVE_JPEG=12,SAVE_REPORT=13;
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setPadding(24,24,24,24);
        ScrollView scroll=new ScrollView(this);scroll.addView(layout);setContentView(scroll);
        TextView heading=new TextView(this);heading.setText("ProofCam Research\nOffline watermark benchmark — not proof of authenticity");heading.setTextSize(20);layout.addView(heading);
        button(layout,"1. Choose test photo",()->choose(PHOTO));
        button(layout,"2. Benchmark (3 warmups + 20 measured runs)",this::benchmark);
        button(layout,"3. Save marked JPEG",()->{if(marked==null||!report.has("measured_trials")){message("Complete a benchmark first.");return;}save(SAVE_JPEG,"image/jpeg","proofcam-research.jpg");});
        attest=new CheckBox(this);attest.setText("I captured the selected screenshot on this phone");layout.addView(attest);
        mediaRectangle=new EditText(this);mediaRectangle.setHint("Optional media rectangle: left,top,right,bottom (pixels)");layout.addView(mediaRectangle);
        button(layout,"4. Decode selected screenshot",()->{if(expected==null||marked==null||!report.has("measured_trials")){message("Complete a benchmark first.");return;}choose(SCREEN);});
        button(layout,"5. Save JSON evidence",()->save(SAVE_REPORT,"application/json","proofcam-research.json"));
        status=new TextView(this);status.setText("Select a test photo. Keep the original and screenshot files with the exported JSON.\nNo files are uploaded. Results stay in memory until you save them.");layout.addView(status);
        preview=new ImageView(this);preview.setAdjustViewBounds(true);preview.setScaleType(ImageView.ScaleType.FIT_CENTER);layout.addView(preview,new LinearLayout.LayoutParams(-1,900));
    }
    private void button(LinearLayout layout,String title,Runnable action) {Button b=new Button(this);b.setText(title);b.setOnClickListener(v->action.run());actions.add(b);layout.addView(b);}
    private void message(String text){status.setText(text);}
    private void busy(boolean value){for(Button b:actions)b.setEnabled(!value);attest.setEnabled(!value);mediaRectangle.setEnabled(!value);}
    private void choose(int request){Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,request);}
    private void save(int request,String mime,String name){Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType(mime).addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,name);startActivityForResult(i,request);}
    private byte[] read(Uri uri)throws Exception {
        try(InputStream in=getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){
            if(in==null)throw new IOException("Cannot read selected file");byte[] buffer=new byte[8192];int n;
            while((n=in.read(buffer))!=-1){if(out.size()+n>25*1024*1024)throw new IOException("25 MiB file limit");out.write(buffer,0,n);}return out.toByteArray();
        }
    }
    private Bitmap decode(byte[] bytes)throws Exception {
        return ImageDecoder.decodeBitmap(ImageDecoder.createSource(ByteBuffer.wrap(bytes)),(decoder,info,src)->{
            String mime=info.getMimeType();int w=info.getSize().getWidth(),h=info.getSize().getHeight();
            if((!mime.equals("image/jpeg")&&!mime.equals("image/png")) || (long)w*h>20000000 || w>16384 || h>16384)
                throw new IllegalArgumentException("JPEG/PNG only; at most 20 megapixels and 16384 pixels per side");
            decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);decoder.setTargetColorSpace(ColorSpace.get(ColorSpace.Named.SRGB));
        });
    }
    private static String sha(byte[] bytes)throws Exception {byte[] hash=MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder s=new StringBuilder();for(byte b:hash)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    private static byte[] jpeg(Bitmap image)throws Exception {ByteArrayOutputStream out=new ByteArrayOutputStream();if(!image.compress(Bitmap.CompressFormat.JPEG,95,out))throw new IOException("JPEG encoding failed");return out.toByteArray();}
    private JSONObject device()throws Exception{return new JSONObject().put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("soc_model",Build.SOC_MODEL).put("os_release",Build.VERSION.RELEASE).put("sdk",Build.VERSION.SDK_INT).put("security_patch",Build.VERSION.SECURITY_PATCH).put("build_fingerprint",Build.FINGERPRINT).put("abis",new JSONArray(Arrays.asList(Build.SUPPORTED_ABIS))).put("app_version","0.1-research").put("apk_sha256",sha(java.nio.file.Files.readAllBytes(new File(getApplicationInfo().sourceDir).toPath()))).put("hardware",Build.HARDWARE);}
    private void recordError(String error){try{report.put("last_error",error);}catch(JSONException ignored){}}
    private void work(Callable<String> task){busy(true);worker.submit(()->{String text;try{text=task.call();}catch(Exception e){text="Failed: "+e.getClass().getSimpleName()+": "+e.getMessage();recordError(text);}catch(OutOfMemoryError e){text="Insufficient memory. Choose a smaller image.";recordError(text);}final String result=text;runOnUiThread(()->{if(isDestroyed())return;busy(false);message(result);});});}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;Uri uri=data.getData();boolean declared=attest.isChecked();String rectangleText=mediaRectangle.getText().toString().trim();
        if(request==SAVE_JPEG||request==SAVE_REPORT){work(()->{byte[] content=request==SAVE_JPEG?marked:report.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8);if(content==null)throw new IOException("No marked export");try(OutputStream out=getContentResolver().openOutputStream(uri)){if(out==null)throw new IOException("Cannot save");out.write(content);}return "Saved locally.";});return;}
        work(()->{
            byte[] bytes=read(uri);Bitmap decoded=decode(bytes);
            if(request==PHOTO){
                if(decoded.hasAlpha()){decoded.recycle();throw new IOException("Choose an opaque JPEG or PNG for this research candidate");}
                source=decoded;marked=null;expected=null;
                report=new JSONObject().put("schema",1).put("status","research_only_not_certification").put("candidate",AndroidCandidate.NAME).put("device",device()).put("input_sha256",sha(bytes)).put("input_width",source.getWidth()).put("input_height",source.getHeight());
                runOnUiThread(()->{if(!isDestroyed()){preview.setImageBitmap(source);attest.setChecked(false);}});return "Photo loaded. Run the benchmark.";
            }
            Bitmap region=decoded;JSONArray selectedRectangle=new JSONArray();
            if(!rectangleText.isEmpty()) {
                String[] parts=rectangleText.split(",");if(parts.length!=4){decoded.recycle();throw new IllegalArgumentException("Enter four rectangle coordinates");}
                int left=Integer.parseInt(parts[0].trim()),top=Integer.parseInt(parts[1].trim()),right=Integer.parseInt(parts[2].trim()),bottom=Integer.parseInt(parts[3].trim());
                if(left<0||top<0||right>decoded.getWidth()||bottom>decoded.getHeight()||right<=left||bottom<=top){decoded.recycle();throw new IllegalArgumentException("Rectangle outside image");}
                selectedRectangle.put(left).put(top).put(right).put(bottom);region=Bitmap.createBitmap(decoded,left,top,right-left,bottom-top);
            }
            long start=System.nanoTime();JSONObject recovery=AndroidCandidate.extract(region);double elapsed=(System.nanoTime()-start)/1e6;
            if(region!=decoded)region.recycle();
            JSONArray ids=recovery.getJSONArray("decoded_ids");boolean correct=ids.length()==1&&expected.equals(ids.getString(0));
            JSONObject screen=new JSONObject().put("sha256",sha(bytes)).put("width",decoded.getWidth()).put("height",decoded.getHeight()).put("elapsed_ms",elapsed).put("region_selection",rectangleText.isEmpty()?"automatic":"manual").put("selected_rectangle",selectedRectangle).put("attempt_coordinates","relative to selected region; original input hash unchanged").put("operator_attested_os_screenshot",declared).put("capture_device_claim",declared?device():JSONObject.NULL).put("recovery",recovery).put("correct_expected_id",correct).put("parent_export_sha256",sha(marked));
            report.put("selected_screenshot",screen);decoded.recycle();
            return "Selected screenshot: "+(correct?"expected ID recovered":"expected ID NOT recovered")+"\nOS screenshot declaration: "+declared+"\nThis is an operator claim, not device-origin attestation. Save JSON and retain the selected screenshot file.";
        });
    }
    private void benchmark(){if(source==null){message("Choose a test photo first.");return;}work(()->{
        String sourceHash=report.getString("input_sha256");
        marked=null;expected=null;report=new JSONObject().put("schema",1).put("status","research_only_not_certification").put("candidate",AndroidCandidate.NAME).put("device",device()).put("input_sha256",sourceHash).put("input_width",source.getWidth()).put("input_height",source.getHeight());
        byte[] random=new byte[16];new SecureRandom().nextBytes(random);StringBuilder text=new StringBuilder();for(byte b:random)text.append(String.format(Locale.ROOT,"%02x",b&255));expected=text.toString();
        int edge=Math.max(source.getWidth(),source.getHeight());double ratio=Math.min(1,1024.0/edge);
        Bitmap normalized=Bitmap.createScaledBitmap(source,Math.max(1,(int)Math.rint(source.getWidth()*ratio)),Math.max(1,(int)Math.rint(source.getHeight()*ratio)),true);
        double[] embedTimes=new double[20],decodeTimes=new double[20];JSONArray trials=new JSONArray();long maxSampledHeap=0;int maxSampledPss=0;int correct=0;
        for(int i=-3;i<20;i++){
            long start=System.nanoTime();Bitmap output=AndroidCandidate.embed(normalized,expected);byte[] encoded=jpeg(output);double em=(System.nanoTime()-start)/1e6;output.recycle();
            Bitmap finalImage=decode(encoded);start=System.nanoTime();JSONObject found=AndroidCandidate.extract(finalImage);double dm=(System.nanoTime()-start)/1e6;finalImage.recycle();
            JSONArray ids=found.getJSONArray("decoded_ids");boolean match=ids.length()==1&&expected.equals(ids.getString(0));
            if(i>=0){embedTimes[i]=em;decodeTimes[i]=dm;if(match)correct++;trials.put(new JSONObject().put("embed_encode_ms",em).put("extract_ms",dm).put("correct",match).put("recovery",found));}
            Runtime runtime=Runtime.getRuntime();maxSampledHeap=Math.max(maxSampledHeap,runtime.totalMemory()-runtime.freeMemory());Debug.MemoryInfo memory=new Debug.MemoryInfo();Debug.getMemoryInfo(memory);maxSampledPss=Math.max(maxSampledPss,memory.getTotalPss());marked=encoded;
        }
        report.put("export_width",normalized.getWidth()).put("export_height",normalized.getHeight()).put("payload_bits",176).put("record_id_bits",128).put("frame_repetitions_min",(normalized.getWidth()/8)*(normalized.getHeight()/8)/176);
        if(normalized!=source)normalized.recycle();Arrays.sort(embedTimes);Arrays.sort(decodeTimes);
        report.remove("selected_screenshot");report.put("expected_id",expected).put("export_sha256",sha(marked)).put("warmups",3).put("measured_trials",trials).put("embed_encode_p95_ms",embedTimes[18]).put("extract_p95_ms",decodeTimes[18]).put("percentile_method","nearest-rank 95th of 20 measured iterations").put("sampled_heap_max_bytes",maxSampledHeap).put("sampled_total_pss_max_kib",maxSampledPss).put("memory_limitation","Post-iteration samples, including warmups; not peak or incremental memory").put("preprocessing","ImageDecoder EXIF/sRGB; opaque inputs; bilinear downscale to at most 1024; Android JPEG quality 95; platform encoder details not pinned");
        Bitmap shown=decode(marked);runOnUiThread(()->{if(!isDestroyed())preview.setImageBitmap(shown);});
        return "Benchmark complete: "+correct+"/20 original IDs recovered\nEmbed+encode p95: "+embedTimes[18]+" ms\nExtract p95: "+decodeTimes[18]+" ms\nSave marked JPEG, display it in your normal photo viewer, capture an OS screenshot, then select that screenshot here. Save JSON last. These are repeated timing trials, not independent recovery samples.";
    });}
    @Override protected void onDestroy(){worker.shutdown();super.onDestroy();}
}
