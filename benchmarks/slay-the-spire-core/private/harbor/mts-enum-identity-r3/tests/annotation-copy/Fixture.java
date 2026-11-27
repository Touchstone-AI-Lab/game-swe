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
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.FIELD) public @interface Mark {String value();int count();Class<?> type();Mode flag();String[] words();}
 public static class One {@SpireEnum(name="NEW") @Mark(value="a/b+c",count=19,type=String[].class,flag=Mode.C,words={"left","right"}) public static Mode VALUE;}
 public static Object run()throws Exception{Mark m=Mode.class.getField("NEW").getAnnotation(Mark.class);return m.value()+":"+m.count()+":"+m.type().getName()+":"+m.flag()+":"+Arrays.toString(m.words());}
}
