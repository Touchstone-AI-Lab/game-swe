package rhenium.mindustry.harness;

import java.util.*;

/** Ordered, frozen list of named cases. */
public final class Suite{
    @FunctionalInterface
    public interface Body{
        void run(Ctx ctx) throws Exception;
    }

    static final class Case{
        final String name;
        final Body body;

        Case(String name, Body body){
            this.name = name;
            this.body = body;
        }
    }

    final List<Case> cases = new ArrayList<>();

    public void test(String name, Body body){
        if(name == null || name.isBlank() || !name.equals(name.strip())){
            throw new IllegalArgumentException("case names must be non-blank without surrounding whitespace");
        }
        for(Case existing : cases){
            if(existing.name.equals(name)) throw new IllegalArgumentException("duplicate case name: " + name);
        }
        cases.add(new Case(name, body));
    }
}
