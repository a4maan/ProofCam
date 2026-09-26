package org.proofcam.benchmark;

import java.util.zip.CRC32;

/** Research QIM12 core. Public IDs and CRC do not authenticate an image. */
public final class DctCore {
    public static final int BITS = 176;
    private static final double[] BASIS = new double[64];
    static {
        for (int y=0;y<8;y++) for (int x=0;x<8;x++)
            BASIS[y*8+x] = .25 * Math.cos((2*y+1)*Math.PI/16) * Math.cos((2*x+1)*2*Math.PI/16);
    }
    private DctCore() {}
    static void validate(int[] pixels, int width, int height) {
        if (width<1 || height<1 || width>16384 || height>16384 || (long)width*height>20000000
                || pixels.length != (long)width*height || (width/8)*(height/8)<BITS*3)
            throw new IllegalArgumentException("Image exceeds bounds or cannot hold three frames");
    }
    static byte[] frame(String id) {
        if (id==null || !id.matches("[0-9a-f]{32}")) throw new IllegalArgumentException("128-bit lowercase hex ID required");
        byte[] bytes=new byte[22]; bytes[0]=80; bytes[1]=67;
        for(int i=0;i<16;i++) bytes[i+2]=(byte)Integer.parseInt(id.substring(i*2,i*2+2),16);
        CRC32 crc=new CRC32(); crc.update(bytes,0,18); long value=crc.getValue();
        for(int i=0;i<4;i++) bytes[18+i]=(byte)(value >>> (24-8*i));
        return bytes;
    }
    static double coefficient(int[] pixels,int width,int bx,int by) {
        double value=0;
        for(int y=0;y<8;y++) for(int x=0;x<8;x++) {
            int p=pixels[(by+y)*width+bx+x];
            value += (.299*((p>>>16)&255)+.587*((p>>>8)&255)+.114*(p&255))*BASIS[y*8+x];
        }
        return value;
    }
    private static int channel(int value,double delta) { return (int)Math.max(0,Math.min(255,Math.rint(value+delta))); }
    public static int[] embed(int[] pixels,int width,int height,String id) {
        validate(pixels,width,height); byte[] payload=frame(id); int[] output=pixels.clone(); int block=0;
        for(int by=0;by+8<=height;by+=8) for(int bx=0;bx+8<=width;bx+=8) {
            int index=(block++)%BITS; int bit=(payload[index/8] >>> (7-index%8))&1;
            double c=coefficient(pixels,width,bx,by); double target=(2*Math.rint((c/12-bit)/2)+bit)*12;
            for(int y=0;y<8;y++) for(int x=0;x<8;x++) {
                int offset=(by+y)*width+bx+x; int p=pixels[offset]; double delta=(target-c)*BASIS[y*8+x];
                output[offset]=0xff000000|(channel((p>>>16)&255,delta)<<16)|(channel((p>>>8)&255,delta)<<8)|channel(p&255,delta);
            }
        }
        return output;
    }
    public static String extract(int[] pixels,int width,int height) {
        validate(pixels,width,height); int[] ones=new int[BITS], total=new int[BITS]; int block=0;
        for(int by=0;by+8<=height;by+=8) for(int bx=0;bx+8<=width;bx+=8) {
            int index=(block++)%BITS; total[index]++;
            ones[index] += Math.floorMod((int)Math.rint(coefficient(pixels,width,bx,by)/12),2);
        }
        byte[] payload=new byte[22];
        for(int i=0;i<BITS;i++) { if(ones[i]*2==total[i]) return null; if(ones[i]*2>total[i]) payload[i/8]|=(byte)(1<<(7-i%8)); }
        if(payload[0]!=80 || payload[1]!=67) return null;
        CRC32 crc=new CRC32(); crc.update(payload,0,18); long stored=0;
        for(int i=18;i<22;i++) stored=(stored<<8)|(payload[i]&255);
        if(crc.getValue()!=stored) return null;
        StringBuilder id=new StringBuilder(); for(int i=2;i<18;i++) id.append(String.format(java.util.Locale.ROOT,"%02x",payload[i]&255));
        return id.toString();
    }
}
