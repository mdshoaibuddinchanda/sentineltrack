import { describe, expect, it } from "vitest";

import { parseCameraCsv } from "../utils/cameraRegistry";

describe("camera registry CSV", () => {
  it("parses quoted organization data and typed GIS fields", () => {
    const records = parseCameraCsv([
      "camera_id,name,organization,latitude,longitude,location_quality,coordinate_source,coverage_radius_m,live",
      'cam-01,"Paldi, Circle","City Police",23.01,72.57,VERIFIED,"Survey register 42",125,true',
    ].join("\n"));

    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      camera_id: "cam-01",
      name: "Paldi, Circle",
      organization: "City Police",
      latitude: 23.01,
      longitude: 72.57,
      location_quality: "VERIFIED",
      coordinate_source: "Survey register 42",
      coverage_radius_m: 125,
      live: true,
    });
  });

  it("does not invent a location quality when GPS is absent", () => {
    const [record] = parseCameraCsv("camera_id,name\ncam-02,No survey yet\n");
    expect(record.location_quality).toBe("UNKNOWN");
    expect(record.latitude).toBeUndefined();
    expect(record.longitude).toBeUndefined();
  });

  it("rejects unsupported headers so spelling mistakes cannot silently discard evidence", () => {
    expect(() => parseCameraCsv("camera_id,latitdue\ncam-03,23.0\n"))
      .toThrow("Unsupported CSV header: latitdue");
  });

  it("rejects invalid booleans and batches above the server limit", () => {
    expect(() => parseCameraCsv("camera_id,live\ncam-04,maybe\n"))
      .toThrow("live must be true or false");

    const rows = ["camera_id", ...Array.from({ length: 501 }, (_, index) => `cam-${index}`)];
    expect(() => parseCameraCsv(rows.join("\n"))).toThrow("limited to 500 records");
  });
});
