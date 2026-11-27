import mindustry.Vars;
import mindustry.content.Blocks;
import mindustry.game.Team;
import mindustry.gen.Building;
import mindustry.mod.Plugin;
import mindustry.world.Block;
import mindustry.world.Tile;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Server-side adapter: observes real buildings and applies single operations to the world. */
public final class BlueprintReconcilerPlugin extends Plugin {
    private static BlueprintReconcilerPlugin instance;
    private final List<LayoutReconciler.Op> applied = new ArrayList<>();

    public BlueprintReconcilerPlugin() {
        instance = this;
    }

    public static BlueprintReconcilerPlugin instance() {
        return instance;
    }

    public LayoutReconciler core(LayoutReconciler.Pricing pricing) {
        return new LayoutReconciler(Vars.world.width(), Vars.world.height(), pricing);
    }

    public List<LayoutReconciler.Cell> observe(int x0, int y0, int x1, int y1) {
        if (x0 > x1 || y0 > y1) throw new IllegalArgumentException("empty rectangle");
        int left = Math.max(x0, 0);
        int bottom = Math.max(y0, 0);
        int right = Math.min(x1, Vars.world.width() - 1);
        int top = Math.min(y1, Vars.world.height() - 1);
        Set<Building> seen = new LinkedHashSet<>();
        for (int y = bottom; y <= top; y++) {
            for (int x = left; x <= right; x++) {
                Tile tile = Vars.world.tile(x, y);
                if (tile != null && tile.build != null) seen.add(tile.build);
            }
        }
        List<LayoutReconciler.Cell> cells = new ArrayList<>();
        for (Building build : seen) {
            cells.add(new LayoutReconciler.Cell(
                build.tile.x, build.tile.y, build.block.name, build.block.size, build.rotation));
        }
        cells.sort(Comparator.comparingInt(LayoutReconciler.Cell::y)
            .thenComparingInt(LayoutReconciler.Cell::x));
        return List.copyOf(cells);
    }

    public boolean apply(LayoutReconciler.Op op, Team team) {
        if (op == null || team == null || op.kind() == null || op.block() == null) return false;
        Block block = Vars.content.block(op.block());
        if (block == null || block.size != op.size() || op.rotation() < 0 || op.rotation() > 3) return false;
        Tile origin = Vars.world.tile(op.x(), op.y());
        if (op.kind() == LayoutReconciler.Kind.PLACE) {
            int left = LayoutReconciler.low(op.x(), op.size());
            int bottom = LayoutReconciler.low(op.y(), op.size());
            for (int dy = 0; dy < op.size(); dy++) {
                for (int dx = 0; dx < op.size(); dx++) {
                    Tile tile = Vars.world.tile(left + dx, bottom + dy);
                    if (tile == null || tile.build != null || tile.block() != Blocks.air) return false;
                }
            }
            origin.setBlock(block, team, op.rotation());
        } else {
            if (origin == null || origin.build == null || origin.build.tile != origin
                || origin.build.block != block) {
                return false;
            }
            if (op.kind() == LayoutReconciler.Kind.REMOVE) {
                origin.setAir();
            } else {
                origin.setBlock(block, origin.build.team, op.rotation());
            }
        }
        applied.add(op);
        return true;
    }

    public Object exportState() {
        return List.copyOf(applied);
    }
}
