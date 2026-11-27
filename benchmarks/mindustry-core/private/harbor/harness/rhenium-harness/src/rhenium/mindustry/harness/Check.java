package rhenium.mindustry.harness;

import java.util.*;

/** Assertions used by grader cases; every failure carries a short, public-facing message. */
public final class Check{
    private Check(){
    }

    public static void isTrue(boolean condition, String message){
        if(!condition) throw new CheckFailure(message);
    }

    public static void isFalse(boolean condition, String message){
        if(condition) throw new CheckFailure(message);
    }

    public static <T> T notNull(T value, String message){
        if(value == null) throw new CheckFailure(message);
        return value;
    }

    public static void equal(Object expected, Object actual, String what){
        if(!Objects.equals(expected, actual)){
            throw new CheckFailure(what + ": expected " + expected + ", got " + actual);
        }
    }

    public static void near(double expected, double actual, double tolerance, String what){
        if(Double.isNaN(actual) || Math.abs(expected - actual) > tolerance){
            throw new CheckFailure(what + ": expected " + expected + " (+/-" + tolerance + "), got " + actual);
        }
    }

    public static void atLeast(double minimum, double actual, String what){
        if(Double.isNaN(actual) || actual < minimum){
            throw new CheckFailure(what + ": expected at least " + minimum + ", got " + actual);
        }
    }

    public static void atMost(double maximum, double actual, String what){
        if(Double.isNaN(actual) || actual > maximum){
            throw new CheckFailure(what + ": expected at most " + maximum + ", got " + actual);
        }
    }

    public static void fail(String message){
        throw new CheckFailure(message);
    }
}
