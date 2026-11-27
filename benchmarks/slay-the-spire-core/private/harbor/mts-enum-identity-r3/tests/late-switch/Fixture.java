package enumfixture;
import com.evacipated.cardcrawl.modthespire.*;
import com.evacipated.cardcrawl.modthespire.lib.*;
import java.util.*;
import java.lang.annotation.*;
public class Fixture {

 public enum Mode { A,B,C }
 public static int select(Mode m){switch(m){case A:return 11;case B:return 22;case C:return 33;default:return 99;}}
 public static class Late {public static int select(Mode m){switch(m){case A:return 111;case B:return 222;case C:return 333;default:return 999;}}}
 public static EnumBusterReflect buster()throws Exception{return new EnumBusterReflect(Fixture.class.getClassLoader(),Mode.class);}
public static Object run()throws Exception{EnumBusterReflect b=buster();Mode first=(Mode)b.make("FIRST");b.addByValue(first);int before=Late.select(first);Mode second=(Mode)b.make("SECOND");b.addByValue(second);return before+":"+Late.select(Mode.C)+":"+Late.select(second);}
}
