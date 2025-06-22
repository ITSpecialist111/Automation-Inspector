import axios from "axios";
import type { DependencyMap } from "./utils/types";

const api = axios.create({
  baseURL: "/",
  headers: { "Cache-Control": "no-store" },
});

/**
 * Fetch the dependency map from the backend.
 * @param force If true, forces a cache refresh.
 */
export async function fetchDependencyMap(
  force = false,
): Promise<DependencyMap> {
  const url = `dependency_map.json${force ? "?force=1" : ""}`;
  const resp = await api.get<DependencyMap>(url);
  return resp.data;
}
