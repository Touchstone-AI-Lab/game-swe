package com.evacipated.cardcrawl.modthespire;

import java.util.*;

// Heavily modified from
// http://www.java2s.com/Code/Java/Collections-Data-Structure/Topologicalsorting.htm
// and
// http://blog.gapotchenko.com/stable-topological-sort
public class GraphTS<T>
{
    class Vertex
    {
        T value;

        Vertex(T v) {
            this.value = v;
        }
    }

    private List<Vertex> vertexList;
    private List<List<Boolean>> matrix;

    public List<T> sortedArray;

    public GraphTS()
    {
        vertexList = new ArrayList<>();
        matrix = new ArrayList<>();
        sortedArray = new ArrayList<>();
    }

    public void addVertex(T v)
    {
        vertexList.add(new Vertex(v));
        List<Boolean> tmp = new ArrayList<>();
        matrix.add(tmp);

        for (List<Boolean> row : matrix) {
            for (int i=row.size(); i<vertexList.size(); ++i) {
                row.add(false);
            }
        }
    }

    public void addEdge(int start, int end)
    {
        matrix.get(start).set(end, true);
    }

    public void displayVertex(int idx) {
        System.out.print(vertexList.get(idx).value);
    }

    public void tsort() throws CyclicDependencyException
    {
        sortedArray.clear();
        while (vertexList.size() > 0) { // while vertices remain,
            // get a vertex with no successors, or -1
            int currentVertex = noSuccessors();
            if (currentVertex == -1) { // must be a cycle
                throw new CyclicDependencyException();
            }
            // insert vertex label in sorted array
            sortedArray.add(vertexList.get(currentVertex).value);

            deleteVertex(currentVertex); // delete vertex
        }

        Collections.reverse(sortedArray);
    }

    public void tsortStable()
    {
        sortedArray.clear();
        for (Vertex v : vertexList) {
            sortedArray.add(v.value);
        }

        int n = sortedArray.size();

        Dependencies depends = new Dependencies();

        boolean restart = false;
        do {
            restart = false;
            for (int i=0; i<n; ++i) {
                for (int j=0; j<i; ++j) {
                    if (depends.doesXHaveDirectDependencyOnY(sortedArray.get(j), sortedArray.get(i))) {
                        boolean iOnJ = depends.doesXHaveTransientDependencyOnY(sortedArray.get(j), sortedArray.get(i));
                        boolean jOnI = depends.doesXHaveTransientDependencyOnY(sortedArray.get(i), sortedArray.get(j));

                        boolean circular = iOnJ && jOnI;
                        if (!circular) {
                            T t = sortedArray.get(i);
                            List<Boolean> children = matrix.get(i);
                            sortedArray.remove(i);
                            matrix.remove(i);
                            sortedArray.add(j, t);
                            matrix.add(j, children);
                            restart = true;
                            break;
                        }
                    }
                }
                if (restart) break;
            }
        } while (restart);
    }

    private int noSuccessors() // returns vert with no successors (or -1 if no such verts)
    {
        boolean isEdge; // edge from row to column in adjMat

        for (int row = 0; row < vertexList.size(); row++) {
            isEdge = false; // check edges
            for (int col = 0; col < vertexList.size(); col++) {
                if (matrix.get(row).get(col)) {// if edge to another,
                    isEdge = true;
                    break; // this vertex has a successor try another
                }
            }
            if (!isEdge) // if no edges, has no successors
                return row;
        }
        return -1; // no
    }

    public void deleteVertex(int delVert)
    {
        vertexList.remove(delVert);

        for (List<Boolean> row : matrix) {
            row.remove(delVert);
        }
        matrix.remove(delVert);
    }

    /**
     * Who requires whom, captured once before sorting starts. An edge added with
     * addEdge(dependency, dependent) is stored as matrix[dependency][dependent].
     */
    private class Dependencies
    {
        private final Map<T, Set<T>> requires = new HashMap<>();

        Dependencies()
        {
            for (int row = 0; row < vertexList.size(); ++row) {
                for (int col = 0; col < vertexList.size(); ++col) {
                    if (row != col && matrix.get(row).get(col)) {
                        T dependency = vertexList.get(row).value;
                        T dependent = vertexList.get(col).value;
                        requires.computeIfAbsent(dependent, k -> new HashSet<>()).add(dependency);
                    }
                }
            }
        }

        boolean doesXHaveDirectDependencyOnY(T x, T y)
        {
            return requires.getOrDefault(x, Collections.emptySet()).contains(y);
        }

        boolean doesXHaveTransientDependencyOnY(T x, T y)
        {
            // Breadth-first over the requirement relation; each walk keeps its own
            // visited set so a cycle ends the walk instead of recursing forever.
            Set<T> seen = new HashSet<>();
            Deque<T> pending = new ArrayDeque<>();
            pending.add(x);
            while (!pending.isEmpty()) {
                T current = pending.poll();
                if (!seen.add(current)) {
                    continue;
                }
                for (T next : requires.getOrDefault(current, Collections.emptySet())) {
                    if (next.equals(y)) {
                        return true;
                    }
                    pending.add(next);
                }
            }
            return false;
        }
    }
}
