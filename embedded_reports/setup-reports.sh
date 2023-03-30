#!/bin/bash
# set -x
###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2021. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################

##
## The script is used to enable the  Grafana Embedded reports feature in Turbonomic installed on OpenShift
##


NAMESPACE=${1}
SECURITYCONTEXT=${2}
REPORTSPASSWORD=""

#1000620000

if [ $# -lt 2 ] 
then
        echo "Usage: <namespace> <security context> <dababase password>"
        echo
        echo "Example: turbonomic 10006500 Passw0rd"
        echo
        echo "Parameter options :"
        echo  "1 <namespace> - The Namespace where Turbonomic is installed"
        echo  "2 <Security Context> - The OpenShift Security Context group?"
   exit 1
fi

#NAMESPACE="turbonomic"

# Prompt user for password for grafana
echo New Grafana Password:
read -s REPORTSPASSWORD

echo $NAMESPACE " " $SECURITYCONTEXT

echo "Creating JSON object for the patch"
cp grafana.template.json grafana.json

sed -i.bak "s|dbpassword|$REPORTSPASSWORD|g" grafana.json
sed -i.bak "s|securitycontext|$SECURITYCONTEXT|g" grafana.json

##
## Enable timescale db pod
##


oc patch Xl xl-release --namespace $NAMESPACE --type merge --patch '{"spec":{"timescaledb":{"enabled":true}}}'

echo "Waiting for timescaldb to become available..."

# Waiting for the timescaledb-db pod to stay in a 1/1 Running state
waitTimescaleDBStatus=$(wait_for_resource_created_by_name pod timescaledb-0 15 $NAMESPACE)
if [ -z "$waitTimescaleDBStatus" ]
then
  echo "Timed out waiting for timescaledb-0 to be created in the $NAMESPACE namespace"
  exit 1
fi

oc patch Xl xl-release --namespace $NAMESPACE --type merge --patch-file grafana.json

echo "Waiting for Grafana to become available..."

# Waiting for the Grafana pod to stay in a 1/1 Running state
waitGrafanaStatus=$(wait_for_resource_created_by_name pod grafana 15 $NAMESPACE)
if [ -z "$waitGrafanaStatus" ]
then
  echo "Timed out waiting for grafana to be created in the $NAMESPACE namespace"
  exit 1
fi

echo "Restarting the Turbonomic api pod..."

# Restarting the API Pod to restart some Turbonomic settings
apiPod=`oc get pod -n $NAMESPACE | grep 'api-' | awk '{print $1}' `
oc delete pod $apiPod -n $NAMESPACE

# wait for a new api pod to create
echo "Waiting for the new api pod to be created..."
sleep 5

# Grab new api pod name for status checking
apiPod=`oc get pod -n $NAMESPACE | grep 'api-' | awk '{print $1}' `

echo "Waiting for the Turbonomic api pod to become available..."
# Waiting for the api pod to stay in a 1/1 Running state
waitAPIStatus=$(wait_for_resource_created_by_name pod "$apiPod" 15 $NAMESPACE)
if [ -z "$waitAPIStatus" ]
then
  echo "Timed out waiting for api pod to be created in the $NAMESPACE namespace"
  exit 1
fi

echo "Finished"

function wait_for_resource_created_by_name {
  local resourceKind=$1
  local name=$2
  local timeToWait=$3
  local namespace=$4
  local TOTAL_WAIT_TIME_SECS=$(( 60 * $timeToWait))
  local CURRENT_WAIT_TIME=0
  local RESOURCE_FULLY_QUALIFIED_NAME=""

  while [ $CURRENT_WAIT_TIME -lt $TOTAL_WAIT_TIME_SECS ]
  do
    POD_STATUS=$(oc get $resourceKind $name -n $namespace| grep Running | cat)
    if [ ! -z "$POD_STATUS" ] 
    then
      # Done waiting 
      break
    fi
    # Still waiting
    sleep 10
    CURRENT_WAIT_TIME=$(( $CURRENT_WAIT_TIME + 10 ))
  done
 
  echo $POD_STATUS 
}

