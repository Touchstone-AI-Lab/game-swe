package enumfixture;
import com.evacipated.cardcrawl.modthespire.*;
import com.evacipated.cardcrawl.modthespire.lib.*;
import java.util.*;
public class Fixture {

 public enum Mode { A,B,C }
 public static String names(Mode[] values){String s="";for(Mode m:values)s+=m.name()+":"+m.ordinal()+";";return s;}
 public static String view(String key,Mode identity){
  String lookup;try{lookup=String.valueOf(Mode.valueOf(key)==identity);}catch(Exception e){lookup=e.getClass().getSimpleName();}
  return "values="+names(Mode.values())+"/constants="+names(Mode.class.getEnumConstants())+"/lookup="+lookup+"/enumset="+EnumSet.allOf(Mode.class);
 }
 public static void warm(){Mode.class.getEnumConstants();Mode.valueOf("A");EnumSet.allOf(Mode.class);}
 public static EnumBusterReflect buster()throws Exception{return new EnumBusterReflect(Fixture.class.getClassLoader(),Mode.class);}
public static Object run()throws Exception{EnumBusterReflect b=buster();Mode original=Mode.B;b.deleteByValue(Mode.B);warm();b.undo();return "restored="+(Mode.B==original)+"/"+view("B",original);}
}
