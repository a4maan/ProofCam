import Foundation

/// Floating-point sRGB luma for geometry search; avoids repeated RGB rounding and allocation.
struct GrayPlane {
    let width: Int, height: Int
    var pixels: [Double]
    init(_ image: RGBImage) {
        width=image.width; height=image.height
        pixels=image.pixels.map { p in 0.299*Double((p>>16)&255)+0.587*Double((p>>8)&255)+0.114*Double(p&255) }
    }
    init(width: Int,height: Int,pixels: [Double]) { self.width=width; self.height=height; self.pixels=pixels }
    func resized(edge: Int) -> GrayPlane {
        let scale=Double(edge)/Double(max(width,height))
        let w=max(1,Int((Double(width)*scale).rounded(.toNearestOrEven))),h=max(1,Int((Double(height)*scale).rounded(.toNearestOrEven)))
        if w==width && h==height { return self }
        var output=[Double](repeating:0,count:w*h)
        for y in 0..<h { for x in 0..<w {
            let sx=min(Double(width-1),max(0,(Double(x)+0.5)*Double(width)/Double(w)-0.5))
            let sy=min(Double(height-1),max(0,(Double(y)+0.5)*Double(height)/Double(h)-0.5))
            output[y*w+x]=sample(sx,sy)
        }}
        return GrayPlane(width:w,height:h,pixels:output)
    }
    func sample(_ x: Double,_ y: Double) -> Double {
        let x0=Int(floor(x)),y0=Int(floor(y)),x1=min(width-1,x0+1),y1=min(height-1,y0+1)
        let fx=x-Double(x0),fy=y-Double(y0)
        return (pixels[y0*width+x0]*(1-fx)+pixels[y0*width+x1]*fx)*(1-fy)+(pixels[y1*width+x0]*(1-fx)+pixels[y1*width+x1]*fx)*fy
    }
    func transformed(degrees: Double,mirrored: Bool=false) -> GrayPlane {
        let a=degrees*Double.pi/180,c=cos(a),s=sin(a),cx=Double(width-1)/2,cy=Double(height-1)/2
        var output=[Double](repeating:0,count:pixels.count)
        for y in 0..<height { for x in 0..<width {
            let dx=Double(x)-cx,dy=Double(y)-cy
            var sx=c*dx+s*dy+cx
            let sy = -s*dx+c*dy+cy
            if mirrored { sx=Double(width-1)-sx }
            if sx>=0 && sy>=0 && sx<=Double(width-1) && sy<=Double(height-1) { output[y*width+x]=sample(sx,sy) }
        }}
        return GrayPlane(width:width,height:height,pixels:output)
    }
    /// Separable DCT(1,1), evaluated at every pixel in O(width*height) using a recurrence.
    func coefficients(block: Int) -> [Double] {
        let n=block,w=width,h=height
        var rows=[Double](repeating:0,count:w*h),result=rows
        guard w>=n,h>=n else { return result }
        let basis=(0..<n).map { sqrt(2/Double(n))*cos(Double(2*$0+1)*Double.pi/Double(2*n)) }
        let factor=2*cos(Double.pi/Double(n)),boundary=basis[0]
        for y in 0..<h {
            for x in 0..<min(2,w-n+1) { for k in 0..<n { rows[y*w+x] += pixels[y*w+x+k]*basis[k] } }
            if w>=n+2 { for x in 0..<w-n-1 { rows[y*w+x+2]=factor*rows[y*w+x+1]-rows[y*w+x]+boundary*(pixels[y*w+x]-pixels[y*w+x+1]+pixels[y*w+x+n]-pixels[y*w+x+n+1]) } }
        }
        for x in 0..<w-n+1 {
            for y in 0..<min(2,h-n+1) { for k in 0..<n { result[y*w+x] += rows[(y+k)*w+x]*basis[k] } }
            if h>=n+2 { for y in 0..<h-n-1 { result[(y+2)*w+x]=factor*result[(y+1)*w+x]-result[y*w+x]+boundary*(rows[y*w+x]-rows[(y+1)*w+x]+rows[(y+n)*w+x]-rows[(y+n+1)*w+x]) } }
        }
        return result
    }
}
