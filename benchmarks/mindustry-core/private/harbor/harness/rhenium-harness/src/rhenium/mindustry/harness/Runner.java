package rhenium.mindustry.harness;

import arc.*;
import arc.files.*;
import arc.math.*;
import arc.util.*;
import mindustry.core.*;
import mindustry.game.*;

import java.io.*;
import java.util.*;

import static mindustry.Vars.*;

/** Runs the frozen suite once and reports it on a single nonce-tagged stdout line. */
final class Runner{
    static final String MARKER = "MINDUSTRY_RESULT ";
    static final String READY = "RHENIUM_HARNESS_READY";
    static final String SUITE_CLASS = "rhenium.mindustry.grader.TaskSuite";
    private static final long CASE_TIMEOUT_MS = Long.getLong("rhenium.harness.caseTimeoutMs", 60_000L);
    private static final long EXIT_GRACE_MS = 15_000L;

    private static volatile String currentCase;
    private static volatile long caseStarted;
    private static volatile boolean reported;
    private static String nonce = "";

    private Runner(){
    }

    static synchronized void start(String mode, String runNonce, ClassLoader loader){
        nonce = runNonce;
        if("bootstrap".equals(mode)){
            System.out.println(READY + " " + Version.buildString());
            System.out.flush();
            exit(0);
            return;
        }
        List<Map<String, Object>> results = new ArrayList<>();
        try{
            if(nonce.length() < 16) throw new IllegalStateException("the harness nonce is missing");
            HarnessSuite definition = (HarnessSuite)Class.forName(SUITE_CLASS, true, loader).getDeclaredConstructor().newInstance();
            Suite suite = new Suite();
            definition.define(suite);
            if(suite.cases.isEmpty()) throw new IllegalStateException("the grader suite defines no cases");
            Fi scratch = Core.files.local("rhenium-scratch");
            scratch.deleteDirectory();
            scratch.mkdirs();
            startWatchdog();
            Time.setDeltaProvider(() -> 1f);
            int index = 0;
            for(Suite.Case item : suite.cases){
                results.add(runCase(item, new Ctx(scratch, index), index));
                index++;
            }
            currentCase = null;
            report(results, null);
        }catch(Throwable error){
            currentCase = null;
            report(results, "harness failure: " + describe(error));
        }
        exit(0);
    }

    private static Map<String, Object> runCase(Suite.Case item, Ctx ctx, int index){
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("name", item.name);
        long started = System.nanoTime();
        currentCase = item.name;
        caseStarted = System.currentTimeMillis();
        try{
            reset();
            Mathf.rand.setSeed(0x5eed0000L + index);
            item.body.run(ctx);
            result.put("passed", true);
            result.put("message", "ok");
        }catch(CheckFailure failure){
            result.put("passed", false);
            result.put("message", failure.getMessage());
        }catch(Throwable error){
            result.put("passed", false);
            result.put("message", describe(error));
        }finally{
            try{
                reset();
            }catch(Throwable ignored){
                //the next case resets again before it starts
            }
        }
        result.put("millis", (System.nanoTime() - started) / 1_000_000L);
        return result;
    }

    private static void reset(){
        if(net.active()) net.closeServer();
        logic.reset();
        state.rules = new Rules();
        Time.delta = 1f;
    }

    private static String describe(Throwable error){
        Throwable root = error;
        while(root.getCause() != null && root.getCause() != root) root = root.getCause();
        String message = root.getMessage();
        StackTraceElement[] trace = root.getStackTrace();
        String where = trace.length > 0 ? " at " + trace[0].getClassName() + "." + trace[0].getMethodName() : "";
        return root.getClass().getSimpleName() + (message == null ? "" : ": " + message) + where;
    }

    private static void startWatchdog(){
        Thread watchdog = new Thread(() -> {
            while(!reported){
                String name = currentCase;
                if(name != null && System.currentTimeMillis() - caseStarted > CASE_TIMEOUT_MS){
                    report(List.of(), "case did not finish within " + CASE_TIMEOUT_MS + " ms: " + name);
                    Runtime.getRuntime().halt(3);
                }
                try{
                    Thread.sleep(250);
                }catch(InterruptedException ignored){
                    return;
                }
            }
        }, "rhenium-harness-watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    private static synchronized void report(List<Map<String, Object>> cases, String fatal){
        if(reported) return;
        reported = true;
        StringBuilder out = new StringBuilder(MARKER).append('{');
        out.append("\"schema\":1,\"nonce\":").append(quote(nonce));
        out.append(",\"game\":").append(quote(Version.buildString()));
        if(fatal != null) out.append(",\"fatal\":").append(quote(fatal));
        out.append(",\"cases\":[");
        for(int i = 0; i < cases.size(); i++){
            Map<String, Object> item = cases.get(i);
            if(i > 0) out.append(',');
            out.append("{\"name\":").append(quote((String)item.get("name")));
            out.append(",\"passed\":").append(Boolean.TRUE.equals(item.get("passed")));
            out.append(",\"message\":").append(quote(String.valueOf(item.get("message"))));
            out.append(",\"millis\":").append(item.getOrDefault("millis", 0L));
            out.append('}');
        }
        out.append("]}");
        PrintStream stream = System.out;
        stream.println(out);
        stream.flush();
    }

    static String quote(String value){
        String text = value == null ? "" : value;
        if(text.length() > 600) text = text.substring(0, 600);
        StringBuilder out = new StringBuilder("\"");
        for(int i = 0; i < text.length(); i++){
            char c = text.charAt(i);
            switch(c){
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if(c < 0x20) out.append(String.format("\\u%04x", (int)c));
                    else out.append(c);
                }
            }
        }
        return out.append('"').toString();
    }

    private static void exit(int status){
        Thread halt = new Thread(() -> {
            try{
                Thread.sleep(EXIT_GRACE_MS);
            }catch(InterruptedException ignored){
                //halt anyway
            }
            Runtime.getRuntime().halt(status);
        }, "rhenium-harness-exit");
        halt.setDaemon(true);
        halt.start();
        Core.app.exit();
    }
}
