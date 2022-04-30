import { ComponentFixture, TestBed } from '@angular/core/testing'

import { BranchStatsComponent } from './branch-stats.component'

describe('BranchStatsComponent', () => {
    let component: BranchStatsComponent
    let fixture: ComponentFixture<BranchStatsComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [BranchStatsComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(BranchStatsComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
