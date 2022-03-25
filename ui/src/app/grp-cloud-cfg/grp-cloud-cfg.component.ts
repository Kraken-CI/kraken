import { Component, OnInit, OnDestroy, Input } from '@angular/core'

import { Subscription } from 'rxjs'

import { ManagementService } from '../backend/api/management.service'

interface DeploymentMethod {
    name: string
    val: number
}

@Component({
    selector: 'app-grp-cloud-cfg',
    templateUrl: './grp-cloud-cfg.component.html',
    styleUrls: ['./grp-cloud-cfg.component.sass'],
})
export class GrpCloudCfgComponent implements OnInit, OnDestroy {
    @Input() deployment: any

    deploymentMethods: DeploymentMethod[]

    // aws
    awsRegions: any[]
    awsInstanceTypes: any[]

    // azure
    azureLocations: any[]
    azureVmSizes: any[]

    private subs: Subscription = new Subscription()

    constructor(protected managementService: ManagementService) {
        this.deploymentMethods = [
            { name: 'Manual', val: 0 },
            // {name: 'SSH', val: 1},
            { name: 'AWS EC2', val: 2 },
            { name: 'AWS ECS Fargate', val: 3 },
            { name: 'Azure VM', val: 4 },
            { name: 'Kubernetes', val: 5 },
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

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    getAwsEc2Regions() {
        if (this.awsRegions.length === 0) {
            this.subs.add(
                this.managementService.getAwsEc2Regions().subscribe((data) => {
                    this.awsRegions = data.items

                    if (this.deployment.aws.region) {
                        this.regionChange()
                    }
                })
            )
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
        this.subs.add(
            this.managementService
                .getAwsEc2InstanceTypes(region)
                .subscribe((data) => {
                    this.awsInstanceTypes = data.items
                })
        )
    }

    getAzureLocations() {
        if (this.azureLocations.length === 0) {
            this.subs.add(
                this.managementService.getAzureLocations().subscribe((data) => {
                    this.azureLocations = data.items

                    if (this.deployment.azure_vm.location) {
                        this.azureLocationChange()
                    }
                })
            )
        }
    }

    azureLocationChange() {
        const location = this.deployment.azure_vm.location
        this.subs.add(
            this.managementService
                .getAzureVmSizes(location)
                .subscribe((data) => {
                    this.azureVmSizes = data.items
                })
        )
    }
}
