import { ComponentFixture, TestBed } from '@angular/core/testing'

import { GrpCloudCfgComponent } from './grp-cloud-cfg.component'

describe('GrpCloudCfgComponent', () => {
    let component: GrpCloudCfgComponent
    let fixture: ComponentFixture<GrpCloudCfgComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [GrpCloudCfgComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(GrpCloudCfgComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
