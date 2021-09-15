import { Component, OnInit, Input } from '@angular/core';

import { ManagementService } from '../backend/api/management.service'

interface DeploymentMethod {
    name: string
    val: number
}

@Component({
  selector: 'app-grp-cloud-cfg',
  templateUrl: './grp-cloud-cfg.component.html',
  styleUrls: ['./grp-cloud-cfg.component.sass']
})
export class GrpCloudCfgComponent implements OnInit {
    @Input() deployment: any

    deploymentMethods: DeploymentMethod[]

    // aws
    awsRegions: any[]
    instanceTypes: any[]

    // azure
    azureLocations: any[]
    azureInstanceTypes: any[]

    constructor(
        protected managementService: ManagementService)
    {
        this.deploymentMethods = [
            { name: 'Manual', val: 0 },
            // {name: 'SSH', val: 1},
            { name: 'AWS EC2', val: 2 },
            { name: 'AWS ECS Fargate', val: 3 },
            { name: 'Azure VM', val: 4},
            // {name: 'Google Cloud Platform', val: 3},
            // {name: 'Digital Ocean', val: 5},
            // {name: 'Linode', val: 6},
        ]

        this.awsRegions = []
        this.azureLocations = []
    }

    ngOnInit(): void {
        if (this.deployment.method === 2 || this.deployment.method === 3) {
            this.getAwsEc2Regions()
        }
        if (this.deployment.method === 4) {
            this.getAzureLocations()
        }
    }

    getAwsEc2Regions() {
        if (this.awsRegions.length === 0) {
            this.managementService.getAwsEc2Regions().subscribe((data) => {
                this.awsRegions = data.items

                if (this.deployment.aws.region) {
                    this.regionChange()
                }
            })
        }
    }

    deploymentMethodChange() {
        if (this.deployment.method === 2 || this.deployment.method === 3) {
            this.getAwsEc2Regions()
        }
        if (this.deployment.method === 4) {
            this.getAzureLocations()
        }
    }

    regionChange() {
        const region = this.deployment.aws.region
        this.managementService
            .getAwsEc2InstanceTypes(region)
            .subscribe((data) => {
                this.instanceTypes = data.items
            })
    }

    getAzureLocations() {
        if (this.azureLocations.length === 0) {
            this.managementService.getAzureLocations().subscribe((data) => {
                this.azureLocations = data.items

                //if (this.deployment.aws.region) {
                //    this.regionChange()
                //}
            })
        }
    }

    azureLocationChange() {
        const location = this.deployment.azure.location
        // this.managementService
        //     .getAwsEc2InstanceTypes(region)
        //     .subscribe((data) => {
        //         this.instanceTypes = data.items
        //     })
    }
}
