package enumobserver;
import com.evacipated.cardcrawl.modthespire.Loader;
import com.vdurmont.semver4j.Semver;
import java.io.File;
public class Runner {
 public static void main(String[] args) throws Exception {
  Loader.MTS_VERSION=new Semver("3.30.3");Loader.setGameVersion("12-18-2022");
  Loader.OUT_JAR=true;Loader.STS_JAR=args[2];Loader.STS_PATCHED_JAR=args[3];
  Loader.runMods(new File[]{new File(args[0])});
  boolean loaded=Loader.getClassPool()!=null && new File(args[3]).isFile();String value="missing",error="none";
  if(loaded)try{
   ClassLoader runtime=Loader.getClassPool().getClassLoader();
   value=String.valueOf(runtime.loadClass("enumfixture.Fixture").getMethod("run").invoke(null));
  }catch(Throwable failure){error=failure.getClass().getName();failure.printStackTrace();}
  System.out.println("ENUM_OBSERVATION "+System.getenv("STS_VERIFY_NONCE")+"|id="+args[1]+",loaded="+loaded+",value="+value+",error="+error);
 }
}
