# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime as dt
import itertools
import os
import xml.etree.ElementTree as ET

from rally.common import utils
from rally.common import version
from rally import consts
from rally.task import exporter


@exporter.configure("junit-xml")
class JUnitXMLExporter(exporter.TaskExporter):
    """Generates task report in JUnit-XML format.

    An example of the report (All dates, numbers, names appearing in this
    example are fictitious. Any resemblance to real things is purely
    coincidental):

      .. code-block:: xml

        <testsuites>
          <!--Report is generated by Rally 0.10.0 at 2017-06-04T05:14:00-->
          <testsuite id="task-uu-ii-dd"
                     errors="0"
                     failures="1"
                     skipped="0"
                     tests="2"
                     time="75.0"
                     timestamp="2017-06-04T05:14:00">
            <testcase classname="CinderVolumes"
                      name="list_volumes"
                      id="workload-1-uuid"
                      time="29.9695231915"
                      timestamp="2017-06-04T05:14:44" />
            <testcase classname="NovaServers"
                      name="list_keypairs"
                      id="workload-2-uuid"
                      time="5"
                      timestamp="2017-06-04T05:15:15">
              <failure>ooops</failure>
            </testcase>
          </testsuite>
        </testsuites>
    """

    def generate(self):
        root = ET.Element("testsuites")
        root.append(ET.Comment("Report is generated by Rally %s at %s" % (
            version.version_string(),
            dt.datetime.utcnow().strftime(consts.TimeFormat.ISO8601))))

        for t in self.tasks_results:
            created_at = dt.datetime.strptime(t["created_at"],
                                              "%Y-%m-%dT%H:%M:%S")
            updated_at = dt.datetime.strptime(t["updated_at"],
                                              "%Y-%m-%dT%H:%M:%S")
            task = {
                "id": t["uuid"],
                "tests": 0,
                "errors": "0",
                "skipped": "0",
                "failures": 0,
                "time": "%.2f" % (updated_at - created_at).total_seconds(),
                "timestamp": t["created_at"],
            }
            test_cases = []
            for workload in itertools.chain(
                    *[s["workloads"] for s in t["subtasks"]]):
                class_name, name = workload["name"].split(".", 1)
                test_case = {
                    "id": workload["uuid"],
                    "time": "%.2f" % workload["full_duration"],
                    "name": name,
                    "classname": class_name,
                    "timestamp": workload["created_at"]
                }
                if not workload["pass_sla"]:
                    task["failures"] += 1
                    test_case["failure"] = "\n".join(
                        [s["detail"]
                         for s in workload["sla_results"]["sla"]
                         if not s["success"]])
                test_cases.append(test_case)

            task["tests"] = str(len(test_cases))
            task["failures"] = str(task["failures"])

            testsuite = ET.SubElement(root, "testsuite", task)
            for test_case in test_cases:
                failure = test_case.pop("failure", None)
                test_case = ET.SubElement(testsuite, "testcase", test_case)
                if failure:
                    ET.SubElement(test_case, "failure").text = failure

        utils.prettify_xml(root)

        raw_report = ET.tostring(root, encoding="utf-8").decode("utf-8")

        if self.output_destination:
            return {"files": {self.output_destination: raw_report},
                    "open": "file://" + os.path.abspath(
                        self.output_destination)}
        else:
            return {"print": raw_report}
