package rhenium.mindustry.harness;

/** A failed assertion inside a grader case. */
public final class CheckFailure extends RuntimeException{
    public CheckFailure(String message){
        super(message);
    }
}
