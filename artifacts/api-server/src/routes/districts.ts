import { Router, type IRouter } from "express";
import { readFileSync } from "fs";
import { join } from "path";
import { GetDistrictsResponse, GetDistrictResponse, GetDistrictParams } from "@workspace/api-zod";

const router: IRouter = Router();

function loadDistrictsData() {
  const possiblePaths = [
    join(process.cwd(), "vulnerability_scores.json"),
    join(process.cwd(), "../..", "vulnerability_scores.json"),
    join("/home/runner/workspace", "vulnerability_scores.json"),
  ];

  for (const p of possiblePaths) {
    try {
      const raw = readFileSync(p, "utf-8");
      return JSON.parse(raw);
    } catch {
      continue;
    }
  }

  return {
    metadata: {
      description: "NYC Food Insecurity Vulnerability Score by Community District",
      total_districts: 0,
      critical_count: 0,
      high_count: 0,
    },
    districts: [],
  };
}

router.get("/districts", (_req, res) => {
  const data = loadDistrictsData();
  const response = GetDistrictsResponse.parse({
    metadata: {
      description: data.metadata.description,
      total_districts: data.metadata.total_districts,
      critical_count: data.metadata.critical_count,
      high_count: data.metadata.high_count,
    },
    districts: data.districts,
  });
  res.json(response);
});

router.get("/districts/:fips", (req, res) => {
  const { fips } = GetDistrictParams.parse(req.params);
  const data = loadDistrictsData();
  const district = data.districts.find((d: { fips: string }) => d.fips === fips);
  if (!district) {
    res.status(404).json({ error: "District not found" });
    return;
  }
  const response = GetDistrictResponse.parse(district);
  res.json(response);
});

export default router;
