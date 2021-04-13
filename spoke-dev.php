<?php
$json = json_decode(file_get_contents("php://input"));

// if (count($json) > 0) {
if (isset($json)) {
  print_r( buildspec($json->region, $json->account));
} elseif (isset($_POST['region']) && (strlen($_POST['account']) > 1)) {
  $buildspec = json_decode(buildspec($_POST['region'], $_POST['account'], $_POST['format']), true);
  if ($buildspec['success'] == 'true') {
    ob_start('ob_gzhandler');
    switch ($_POST['format']) {
      case 'cf':
        header('Content-type: text/yaml');
        header('Content-disposition: attachment; filename="' . $_POST['account'] . '.yaml"');
        break;
      case 'tf':
        header('Content-type: text/json');
        header('Content-disposition: attachment; filename="' . $_POST['account'] . '.tf"');
        break;
    }
    echo $buildspec['buildspec'];
  } else {
    print_help($buildspec['code'], $buildspec['data']['description']);
  }
} else {
  print_help();
}

function buildspec($region, $account, $format) {
  $output = null;
  $retval = null;
  switch ($format) {
    case 'cf':
      $template = '/var/netops/aws/spoke-dev.yaml';
      break;
    case 'tf':
      $template = '/var/netops/aws/spoke-dev.tf';
      break;
  }
  $cmd = sprintf('/usr/local/bin/spoke-dev.py %s %s %s', $region, $account, $template);
  exec($cmd, $output, $retval);
  if ($retval <> 0) {
    return sprintf("Error %d", $retval);
  } else {
    return $output[0];
  }
}

function print_form() {
  $output = "
  <p>Or use this form to download the buildspec manually.</p>
  <form method=\"post\" action=\"" . $_SERVER['PHP_SELF'] . "\">
    <table>
    <tr>
      <td colspan=2>Select region:<br />
        <input type=\"radio\" name=\"region\" value=\"ap-southeast-2\">Asia Pacific (Sydney) ap-southeast-2<br />
        <input type=\"radio\" name=\"region\" value=\"eu-central-1\">Europe (Frankfurt) eu-central-1<br />
        <input type=\"radio\" name=\"region\" value=\"eu-west-1\">Europe (Ireland) eu-west-1<br />
        <input type=\"radio\" name=\"region\" value=\"eu-west-2\">Europe (London) eu-west-2<br />
        <input type=\"radio\" name=\"region\" value=\"us-east-1\">US East (N. Virginia) us-east-1
      </td>
    </tr>
    <tr>
      <td colspan=2>
        <input type=\"radio\" name=\"format\" value=\"cf\">CloudFormation<br />
        <input type=\"radio\" name=\"format\" value=\"tf\" checked=\"checked\">Terraform
      </td>
    </tr>
    <tr>
      <td>Account Name:</td>
      <td><input type=\"text\" name=\"accountName\"></td>
    </tr>
    <tr>
      <td>Account Number:</td>
      <td><input type=\"text\" name=\"accountNumber\"></td>
    </tr>
    <tr>
      <td>Business Segment</td>
      <td><input type=\"text\" name=\"businessSegment\"></td>
    </tr>
    <tr>
      <td>Business Department</td>
      <td><input type=\"text\" name=\"businessDepartment\"></td>
    </tr>
    <tr>
      <td>Cost Center</td>
      <td><input type=\"text\" name=\"costCenter\"></td>
    </tr>
    </table>
    <input type=\"submit\" value=\"Submit\">
  </form>
";
  return $output;
}

function print_help($errcode = 0, $errmsg = '') {
  $output  = "<html>
<head>
  <title>IPAM API</title>
  <script src=\"https://cdn.jsdelivr.net/gh/google/code-prettify@master/loader/run_prettify.js\"></script>
  <style>
    dt {font-weight: bold;}
  </style>
</head>
<body>";
  if ($errmsg !== '') {
    $output .= sprintf("
  <h1>Error %s: %s</h1>", $errcode, $errmsg);
  }
  $output .= " 
  <h1><center>spoke.php</center></h1>
  <br>
  <p>This API requests a subnet for a Spoke VPC and updates <a href=\"https://phpipam.hcch.com/\">phpIPAM</a>.</p>
  <p>All input is expected by POST method encoded as JSON.</p>
  <p>Output is a JSON string containing:
    <ol>
    <li>Response codes, processing time</li>
    <li>ID, IP range and description of VPC</li>
    <li>ID, IP range and description of Private subnet A</li>
    <li>ID, IP range and description of Private subnet B</li>
    <li>ID, IP range and description of Transit subnet B</li>
    <li>ID, IP range and description of Transit subnet A</li>
    <li>YAML to feed into CloudFormation</li>
    </ol>
  </p>
  <p>
  The CloudFormation YAML does the following:<br>
  <ol>
  <li>Creation of the VPC</li>
  <li>Creation of the DHCP Options</li>
  <li>Creation of 2 Private Subnets</li>
  <li>Creation of 2 Transit Subnets</li>
  <li>Creation of 2 Private Route Tables (AZ A, AZ B)</li>
  <li>Creation of the Transit Gateway Attachment</li>
  <li>Configuration of default routes into both Route Tables</li>
  </ol>
  </p>
  <p>The following variables are required:</p>
  <dl>
    <dt>account</dt>
    <dd>The name of the account</dd>
    <dt>region</dt>
    <dd>The region where the spoke will reside</dd>
  </dl>
  <p>Example Python 3 code:</p>
  <pre class=\"prettyprint lang-py\">
import requests

url = \"http://gblon-l-pvd01.hcch.com/api/spoke.php\"
headers = {
  'Authorization': 'Basic bmV0b3BzOkN5dDBza2UhZXRvbg==',
  'Content-Type': 'application/json'
}
payload=\"{\\\"region\\\": \\\"eu-west-1\\\", \\\"account\\\": \\\"Testing123\\\"}\"

response = requests.request(\"POST\", url, headers=headers, data=payload)

print(response.text)
  </pre>
  <br />" . print_form() . "
</body>
</html>";
  print $output;
  exit();
}


?>
