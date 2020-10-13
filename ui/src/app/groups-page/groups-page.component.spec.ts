import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { GroupsPageComponent } from './groups-page.component'

describe('GroupsPageComponent', () => {
    let component: GroupsPageComponent
    let fixture: ComponentFixture<GroupsPageComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [GroupsPageComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(GroupsPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
