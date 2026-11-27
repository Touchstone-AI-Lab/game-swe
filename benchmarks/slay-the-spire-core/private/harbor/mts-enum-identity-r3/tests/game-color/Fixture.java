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
public static Object run()throws Exception{
  Class<com.megacrit.cardcrawl.cards.AbstractCard.CardColor> type=com.megacrit.cardcrawl.cards.AbstractCard.CardColor.class;
  int before=type.getEnumConstants().length;Enum.valueOf(type,"RED");
  EnumBusterReflect b=new EnumBusterReflect(Fixture.class.getClassLoader(),type);Enum<?> m=b.make("LOCAL_SCOUT");b.addByValue(m);
  int values=com.megacrit.cardcrawl.cards.AbstractCard.CardColor.values().length;int constants=type.getEnumConstants().length;
  String lookup;try{lookup=String.valueOf(Enum.valueOf(type,"LOCAL_SCOUT")==m);}catch(Exception e){lookup=e.getClass().getSimpleName();}
  return "before="+before+"/values="+values+"/constants="+constants+"/lookup="+lookup+"/set="+EnumSet.allOf(type).size();}
}
