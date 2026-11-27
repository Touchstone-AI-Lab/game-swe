FROM gcb-l4d2-sourcemod-verifier:23990100-sm1.12.7246

USER root
COPY --chmod=755 test.sh verify.py /tests/
COPY suite.sp reward_suite.sp mutant_tanks.cfg mutant_tanks-warp.cfg mutant_tanks-lifecycle.cfg mutant_tanks-hypno.cfg mutant_tanks-panic-fallback.cfg mutant_tanks-rainbow.cfg mutant_tanks-cooldown.cfg mutant_tanks-reward-stack.cfg /tests/
COPY include/ /tests/include/
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
