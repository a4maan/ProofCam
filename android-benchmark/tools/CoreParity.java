package org.proofcam.benchmark;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class CoreParity {
    static int[] read(Path path)throws Exception {
        try(DataInputStream in=new DataInputStream(new BufferedInputStream(Files.newInputStream(path)))){int w=in.readInt(),h=in.readInt();int[] p=new int[w*h+2];p[0]=w;p[1]=h;for(int i=2;i<p.length;i++)p[i]=0xff000000|(in.readUnsignedByte()<<16)|(in.readUnsignedByte()<<8)|in.readUnsignedByte();return p;}
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);
        for(String line:Files.readAllLines(root.resolve("jobs.tsv"))) {
            String[] parts=line.split("\t");int[] raw=read(root.resolve(parts[0]+".rgb"));int w=raw[0],h=raw[1];int[] pixels=Arrays.copyOfRange(raw,2,raw.length);
            int[] python=read(root.resolve(parts[0]+"-python.rgb"));String recovered=DctCore.extract(Arrays.copyOfRange(python,2,python.length),w,h);
            if(!parts[1].equals(recovered))throw new AssertionError("Python to Java recovery failed");
            int[] encoded=DctCore.embed(pixels,w,h,parts[1]);if(!parts[1].equals(DctCore.extract(encoded,w,h)))throw new AssertionError("Java roundtrip failed");
            try(DataOutputStream out=new DataOutputStream(new BufferedOutputStream(Files.newOutputStream(root.resolve(parts[0]+"-java.rgb"))))){out.writeInt(w);out.writeInt(h);for(int p:encoded){out.writeByte(p>>>16);out.writeByte(p>>>8);out.writeByte(p);}}
        }
        int[] gray=new int[512*512];Arrays.fill(gray,0xff808080);if(DctCore.extract(gray,512,512)!=null)throw new AssertionError("Flat negative detected");
        try{DctCore.embed(gray,512,512,"abc");throw new AssertionError("Invalid ID accepted");}catch(IllegalArgumentException expected){}
        try{DctCore.extract(new int[64*64],64,64);throw new AssertionError("Insufficient capacity accepted");}catch(IllegalArgumentException expected){}
        System.out.println("Java core cross-language roundtrips and negative/input guards passed.");
    }
}
